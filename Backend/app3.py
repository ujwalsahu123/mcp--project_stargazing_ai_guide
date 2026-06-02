import asyncio

import streamlit as st

from client3 import auto_fetch_location, start_chatbot_bootstrap, stream_llm_chat_turn


INTRO_MESSAGE = """Hi, I’m AstroGuide. I can help you explore the sky above you, learn about stars and planets, and plan for stargazing tonight.

Try a demo question like:
- Find the brightest stars and planets above me
- Tell me the mythological significance of Mars and Venus
- Show the current position of the Sun and Moon above me
- Give me a weather forecast for stargazing tonight
"""


def _init_state():
	st.session_state.setdefault("lat", 0.0)
	st.session_state.setdefault("lon", 0.0)
	st.session_state.setdefault("alti", 0.0)
	st.session_state.setdefault("location_message", "")
	st.session_state.setdefault("location_error", "")
	st.session_state.setdefault("started", False)
	st.session_state.setdefault("connection_state", "idle")
	st.session_state.setdefault("connection_message", "")
	st.session_state.setdefault("connection_error", "")
	st.session_state.setdefault("connect_future", None)
	st.session_state.setdefault("llm_with_tools", None)
	st.session_state.setdefault("bootstrap_ready", False)
	st.session_state.setdefault("chat_messages", [])
	st.session_state.setdefault("pending_user_text", "")


def _format_location_message(geo):
	city = geo.get("city")
	country = geo.get("country")
	place = ", ".join([part for part in [city, country] if part])
	if place:
		return f"Location filled from IP lookup: {place}."
	return "Location filled from IP lookup."


def _on_auto_fetch_location():
	geo = auto_fetch_location()
	if geo.get("error"):
		st.session_state["location_error"] = f"Could not auto-fetch location: {geo['error']}"
		st.session_state["location_message"] = ""
		return

	if geo.get("latitude") is not None:
		st.session_state["lat"] = float(geo["latitude"])
	if geo.get("longitude") is not None:
		st.session_state["lon"] = float(geo["longitude"])

	st.session_state["location_message"] = _format_location_message(geo)
	st.session_state["location_error"] = ""


def _on_start():
	st.session_state["connection_state"] = "connecting"
	st.session_state["connection_message"] = "Connecting to MCP server..."
	st.session_state["connection_error"] = ""
	st.session_state["connect_future"] = start_chatbot_bootstrap(
		lat=float(st.session_state["lat"]),
		lon=float(st.session_state["lon"]),
		alti=float(st.session_state.get("alti") or 0.0),
	)
	st.session_state["started"] = True
	st.session_state["bootstrap_ready"] = False
	st.session_state["llm_with_tools"] = None
	st.session_state["chat_messages"] = []
	st.session_state["pending_user_text"] = ""


def _poll_connection():
	future = st.session_state.get("connect_future")
	if not future or not future.done():
		return

	try:
		result = future.result()
	except Exception as exc:
		st.session_state["connection_state"] = "error"
		st.session_state["connection_message"] = ""
		st.session_state["connection_error"] = f"MCP server error: {exc}"
		st.session_state["connect_future"] = None
		return

	if isinstance(result, dict) and result.get("error"):
		st.session_state["connection_state"] = "error"
		st.session_state["connection_message"] = ""
		st.session_state["connection_error"] = result["error"]
		st.session_state["connect_future"] = None
		return

	st.session_state["connection_state"] = "connected"
	st.session_state["connection_message"] = "MCP server connected."
	st.session_state["connection_error"] = ""
	st.session_state["connect_future"] = None
	st.session_state["llm_with_tools"] = result.get("llm_with_tools")
	st.session_state["chat_messages"] = [{"role": "assistant", "content": INTRO_MESSAGE}]
	st.session_state["bootstrap_ready"] = True


@st.fragment(run_every=1)
def _connection_status_fragment():
	if not st.session_state.get("started"):
		return

	future = st.session_state.get("connect_future")
	if not future:
		if st.session_state.get("connection_state") == "connected":
			st.success(st.session_state.get("connection_message", "MCP server connected."))
		elif st.session_state.get("connection_state") == "error":
			st.error(st.session_state.get("connection_error", "MCP server error."))
		return

	if future.done():
		_poll_connection()
		st.rerun()

	st.info("Connecting to MCP server...")


def _render_chat_card():
	with st.container(border=True):
		st.subheader("Chatbot")

		chat_ready = st.session_state.get("connection_state") == "connected" and st.session_state.get("bootstrap_ready")

		for msg in st.session_state["chat_messages"]:
			with st.chat_message(msg["role"], avatar="😀" if msg["role"] == "user" else None):
				st.markdown(msg["content"])

		if not st.session_state.get("started"):
			st.caption("Connect to continue.")
			return

		if not chat_ready:
			st.caption("Connecting to MCP server...")
			return

		pending_user_text = st.session_state.get("pending_user_text", "").strip()
		if pending_user_text:
			st.session_state["pending_user_text"] = ""

			with st.chat_message("user", avatar="😀"):
				st.markdown(pending_user_text)

			with st.chat_message("assistant"):
				pipeline_placeholder = st.empty()
				assistant_placeholder = st.empty()
				pipeline_steps = []

				def _render_pipeline(message):
					pipeline_steps.append(message)
					pipeline_placeholder.markdown(
						"\n".join(f"- {step}" for step in pipeline_steps)
					)

				def _render_delta(text):
					assistant_placeholder.markdown(text)

				assistant_text = asyncio.run(
					stream_llm_chat_turn(
						user_prompt=pending_user_text,
						lat=float(st.session_state["lat"]),
						lon=float(st.session_state["lon"]),
						alti=float(st.session_state.get("alti") or 0.0),
						chat_messages=st.session_state["chat_messages"],
						llm_with_tools=st.session_state["llm_with_tools"],
						on_delta=_render_delta,
						on_status=_render_pipeline,
					)
				)
				assistant_placeholder.markdown(assistant_text)

			st.session_state["chat_messages"].append({"role": "user", "content": pending_user_text})
			st.session_state["chat_messages"].append({"role": "assistant", "content": assistant_text})

		with st.form("chat_composer", clear_on_submit=True):
			composer_col, send_col = st.columns([6, 1])
			with composer_col:
				user_text = st.text_input(
					"Ask astronomy question...",
					label_visibility="collapsed",
					placeholder="Ask astronomy question...",
				)
			with send_col:
				send_pressed = st.form_submit_button("Send", use_container_width=True)

		if not send_pressed:
			return

		user_text = user_text.strip()
		if not user_text:
			return

		st.session_state["pending_user_text"] = user_text
		st.rerun()


def main():
	st.set_page_config(page_title="StarGuide MCP Client", page_icon="🌌", layout="wide")
	_init_state()
	_poll_connection()
	st.markdown(
		"""
		<style>
		div[data-testid="stButton"] button[kind="primary"] {
			background: #b91c1c;
			border-color: #b91c1c;
			color: white;
		}
		div[data-testid="stButton"] button[kind="primary"]:hover {
			background: #991b1b;
			border-color: #991b1b;
			color: white;
		}
		</style>
		""",
		unsafe_allow_html=True,
	)

	st.title("StarGuide MCP Client")
	st.caption("Enter your location, connect to the MCP server, then chat with the astronomy assistant.")

	with st.container(border=True):
		st.subheader("Location & Session Inputs")

		col1, col2 = st.columns(2)
		with col1:
			st.number_input("Latitude", key="lat", format="%.6f")
		with col2:
			st.number_input("Longitude", key="lon", format="%.6f")

		st.number_input("Altitude (meters, optional)", key="alti", format="%.2f")

		st.button("Auto Fetch Location", use_container_width=True, on_click=_on_auto_fetch_location)

		if st.session_state["location_message"]:
			st.success(st.session_state["location_message"])
		if st.session_state["location_error"]:
			st.error(st.session_state["location_error"])

		st.button("Connect", type="primary", use_container_width=True, on_click=_on_start)

		_connection_status_fragment()

		if st.session_state.get("connection_state") == "error":
			st.error(st.session_state.get("connection_error", "MCP server error."))

	_render_chat_card()


if __name__ == "__main__":
	main()