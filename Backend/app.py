import asyncio
import html
import json
import re

import streamlit as st

from client import (
	auto_fetch_location,
	call_tool,
	current_iso_time,
	fetch_tools_info,
	start_connection_bootstrap,
	stream_llm_chat_turn,
)


INTRO_MESSAGE = """Hi, I'm AstroGuide. I can help you explore the sky above you, learn about stars and planets, and plan for stargazing tonight.

Try a demo question like:
- Find the brightest stars and planets above me
- Tell me the mythological significance of Mars and Venus
- Show the current position of the Sun and Moon above me
- Give me a weather forecast for stargazing tonight
"""

_JSON_TOKEN_RE = re.compile(
	r'(?P<key>"(?:\\.|[^"\\])*"(?=\s*:))|(?P<string>"(?:\\.|[^"\\])*")|(?P<number>\b-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?\b)|(?P<bool>\btrue\b|\bfalse\b)|(?P<null>\bnull\b)'
)


def _json_html(value):
	pretty = json.dumps(value, indent=2, ensure_ascii=False, default=str)

	def _wrap(css_class, text):
		return f'<span class="{css_class}">{html.escape(text)}</span>'

	def _replace(match):
		if match.group("key"):
			return _wrap("json-key", match.group("key"))
		if match.group("string"):
			return _wrap("json-string", match.group("string"))
		if match.group("number"):
			return _wrap("json-number", match.group("number"))
		if match.group("bool"):
			return _wrap("json-bool", match.group("bool"))
		if match.group("null"):
			return _wrap("json-null", match.group("null"))
		return html.escape(match.group(0))

	return _JSON_TOKEN_RE.sub(_replace, pretty)


def _render_json_panel(value):
	st.html(f'<div class="json-output-box"><pre>{_json_html(value)}</pre></div>')


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
	st.session_state.setdefault("tools", [])
	st.session_state.setdefault("selected_tool", None)
	st.session_state.setdefault("object_name", "Sun")
	st.session_state.setdefault("last_result", None)
	st.session_state.setdefault(
		"output_text",
		json.dumps({"output": None, "message": "Call the tool for output..."}, indent=2),
	)
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
	st.session_state["connect_future"] = start_connection_bootstrap(
		lat=float(st.session_state["lat"]),
		lon=float(st.session_state["lon"]),
		alti=float(st.session_state.get("alti") or 0.0),
	)
	st.session_state["started"] = True
	st.session_state["tools"] = []
	st.session_state["last_result"] = None
	st.session_state["output_text"] = json.dumps(
		{"output": None, "message": "Call the tool for output..."},
		indent=2,
	)
	st.session_state["llm_with_tools"] = None
	st.session_state["bootstrap_ready"] = False
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
	st.session_state["tools"] = result.get("tools_info") or []
	st.session_state["llm_with_tools"] = result.get("llm_with_tools")
	st.session_state["chat_messages"] = [{"role": "assistant", "content": INTRO_MESSAGE}]
	st.session_state["bootstrap_ready"] = True

	if not st.session_state["tools"]:
		st.session_state["tools"] = asyncio.run(fetch_tools_info())
	if not st.session_state["selected_tool"] and st.session_state["tools"]:
		st.session_state["selected_tool"] = st.session_state["tools"][0]["name"]


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


def _build_tool_args(tool_name):
	lat = float(st.session_state["lat"])
	lon = float(st.session_state["lon"])
	alti = float(st.session_state.get("alti") or 0.0)
	latest_time = current_iso_time()

	if tool_name == "health_check":
		return {}
	if tool_name == "visible_objects":
		return {"lat": lat, "lon": lon, "time": latest_time, "alti": alti}
	if tool_name == "object_position":
		return {
			"object_name": st.session_state.get("object_name", "Sun"),
			"lat": lat,
			"lon": lon,
			"time": latest_time,
			"alti": alti,
		}
	if tool_name == "object_detail":
		return {"object_name": st.session_state.get("object_name", "Sun")}
	if tool_name == "weather_forecast":
		return {"lat": lat, "lon": lon}

	return {"lat": lat, "lon": lon, "time": latest_time, "alti": alti}


async def fetch_tool_result(tool_name, args):
	return await call_tool(tool_name, args)


def _render_input_card():
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


def _render_manual_tool_card():
	with st.container(border=True):
		st.subheader("Manual Tool Call")

		if st.session_state["connection_state"] != "connected":
			st.info("Connect to MCP server to load and use tools.")
			return

		if not st.session_state["tools"]:
			st.session_state["tools"] = asyncio.run(fetch_tools_info())

		tool_options = [tool["name"] for tool in st.session_state["tools"]]
		selected_index = 0
		if st.session_state.get("selected_tool") in tool_options:
			selected_index = tool_options.index(st.session_state["selected_tool"])

		st.markdown('<div class="tool-select">', unsafe_allow_html=True)
		selected_name = st.selectbox(
			"Tool",
			tool_options,
			index=selected_index,
			format_func=lambda name: next(
				f"{tool['name']}  -  {tool['short_description']}"
				for tool in st.session_state["tools"]
				if tool["name"] == name
			),
			help="Pick any MCP tool to call manually.",
		)
		st.markdown("</div>", unsafe_allow_html=True)
		st.session_state["selected_tool"] = selected_name

		if selected_name in {"object_position", "object_detail"}:
			st.text_input("Object name", key="object_name", value=st.session_state.get("object_name", "Sun"))

		if st.button("Call", type="primary", use_container_width=True):
			args = _build_tool_args(selected_name)
			result = asyncio.run(fetch_tool_result(selected_name, args))
			st.session_state["last_result"] = {"tool": selected_name, "args": args, "result": result}
			st.session_state["output_text"] = json.dumps(st.session_state["last_result"], indent=2, default=str)

		if st.session_state["output_text"]:
			st.markdown("### Output")
			_render_json_panel(st.session_state["last_result"] or json.loads(st.session_state["output_text"]))


def _render_chat_card():
	with st.container(border=True):
		st.subheader("Chatbot")

		chat_ready = st.session_state.get("connection_state") == "connected" and st.session_state.get("bootstrap_ready")

		for msg in st.session_state["chat_messages"]:
			with st.chat_message(msg["role"]):
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

			with st.chat_message("user"):
				st.markdown(pending_user_text)

			with st.chat_message("assistant"):
				pipeline_placeholder = st.empty()
				assistant_placeholder = st.empty()
				pipeline_steps = []

				def _render_pipeline(message):
					pipeline_steps.append(message)
					pipeline_placeholder.markdown("\n".join(f"- {step}" for step in pipeline_steps))

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
	st.set_page_config(page_title="StarGuide MCP Client", page_icon="*", layout="wide")
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
		.tool-select [data-baseweb="select"] > div {
			min-height: 44px;
		}
		.tool-select [data-baseweb="select"] input {
			font-size: 0.98rem;
		}
		.json-output-box {
			max-height: 340px;
			overflow: auto;
			border: 1px solid rgba(49, 51, 63, 0.18);
			border-radius: 10px;
			background: #fff;
			padding: 12px 14px;
			box-sizing: border-box;
		}
		.json-output-box pre {
			margin: 0;
			white-space: pre;
			line-height: 1.45;
			font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
			font-size: 0.92rem;
		}
		.json-output-box .json-key { color: #7c3aed; }
		.json-output-box .json-string { color: #15803d; }
		.json-output-box .json-number { color: #1d4ed8; }
		.json-output-box .json-bool { color: #b45309; }
		.json-output-box .json-null { color: #dc2626; }
		</style>
		""",
		unsafe_allow_html=True,
	)

	st.title("StarGuide MCP Client")
	st.caption("Enter your location, connect to the MCP server, then call tools manually or chat with the astronomy assistant.")

	_render_input_card()
	_render_manual_tool_card()
	_render_chat_card()


if __name__ == "__main__":
	main()
