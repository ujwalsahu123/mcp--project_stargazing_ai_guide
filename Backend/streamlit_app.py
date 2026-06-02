import asyncio
import base64
import html
import json
import re
from pathlib import Path

import streamlit as st

from streamlit_client import (
	auto_fetch_location,
	call_tool,
	current_iso_time,
	fetch_tools_info,
	start_connection_bootstrap,
	stream_llm_chat_turn,
)


INTRO_MESSAGE = """Hi, I'm AstroGuide. I can help you explore the sky above you, learn about stars and planets, and plan for stargazing tonight.

Try a demo question like:
- Give me a weather forecast for stargazing tonight
- Find the top 10 brightest stars and planets above me
- Show the current position of the Sun and Moon above me
- Tell me the mythological significance of Mars and Venus
or Run all these queries at once 😎
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


def _render_center_notice(message, tone="success"):
	st.markdown(
		f"""
		<div class="center-notice {tone}">
			{html.escape(message)}
		</div>
		""",
		unsafe_allow_html=True,
	)


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
	st.session_state.setdefault("object_name", "Moon")
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

	# Ensure a sensible default selection for manual tool calls.
	# Prefer `object_position` when available so manual card opens with that selected.
	if not st.session_state["tools"]:
		st.session_state["tools"] = asyncio.run(fetch_tools_info())
	if not st.session_state.get("selected_tool") and st.session_state["tools"]:
		names = [t.get("name") for t in st.session_state["tools"]]
		# Prefer weather forecast as the default selected tool when available.
		if "weather_forecast" in names:
			st.session_state["selected_tool"] = "weather_forecast"
		elif "object_position" in names:
			st.session_state["selected_tool"] = "object_position"
		elif "object_detail" in names:
			st.session_state["selected_tool"] = "object_detail"
		else:
			st.session_state["selected_tool"] = st.session_state["tools"][0]["name"]


@st.fragment(run_every=1)
def _connection_status_fragment():
	if not st.session_state.get("started"):
		return

	future = st.session_state.get("connect_future")
	if not future:
		if st.session_state.get("connection_state") == "connected":
			_render_center_notice(st.session_state.get("connection_message", "MCP server connected."), "success")
		elif st.session_state.get("connection_state") == "error":
			_render_center_notice(st.session_state.get("connection_error", "MCP server error."), "error")
		return

	if future.done():
		_poll_connection()
		st.rerun()

	_render_center_notice("Connecting to MCP server...", "info")


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
			"object_name": st.session_state.get("object_name", "Moon"),
			"lat": lat,
			"lon": lon,
			"time": latest_time,
			"alti": alti,
		}
	if tool_name == "object_detail":
		return {"object_name": st.session_state.get("object_name", "Moon")}
	if tool_name == "weather_forecast":
		return {"lat": lat, "lon": lon}

	return {"lat": lat, "lon": lon, "time": latest_time, "alti": alti}


async def fetch_tool_result(tool_name, args):
	return await call_tool(tool_name, args)


def _render_input_card():
	with st.container(border=True):

		st.markdown('<div class="card-heading">Session Location</div>',    unsafe_allow_html=True)
		st.caption("Set the observer position used for manual tools and chatbot answers.")

		col1, col2 = st.columns(2)
		with col1:
			st.number_input("Latitude", key="lat", format="%.6f")
		with col2:
			st.number_input("Longitude", key="lon", format="%.6f")

		st.number_input("Altitude (meters, optional)", key="alti", format="%.2f")
		st.button("Auto Fetch Location", use_container_width=True, on_click=_on_auto_fetch_location)

		if st.session_state["location_message"]:
			_render_center_notice(st.session_state["location_message"], "success")
		if st.session_state["location_error"]:
			_render_center_notice(st.session_state["location_error"], "error")

		st.button("Connect", type="primary", use_container_width=True, on_click=_on_start)
		_connection_status_fragment()


def _render_manual_tool_card():
	with st.container(border=True):
		st.markdown('<div class="card-heading">Manual Tool Call</div>', unsafe_allow_html=True)
		st.caption("Inspect MCP tools directly with the current session inputs.")
		st.caption("NOTE: Visible_Objects tool may take 30 seconds to run on First Try")

		if st.session_state["connection_state"] != "connected":
			_render_center_notice("Connect to MCP server to load and use tools.", "info")
			return

		if not st.session_state["tools"]:
			st.session_state["tools"] = asyncio.run(fetch_tools_info())

		tool_options = [tool["name"] for tool in st.session_state["tools"]]

		# Reorder tools so common tools appear first and visible_objects is last.
		# Desired order: object_detail, object_position, weather_forecast, ...others..., visible_objects
		preferred = ["object_detail", "object_position", "weather_forecast"]
		reordered = []

		for p in preferred:
			if p in tool_options:
				reordered.append(p)

		for t in tool_options:
			if t in preferred or t == "visible_objects":
				continue
			if t not in reordered:
				reordered.append(t)

		if "visible_objects" in tool_options:
			reordered.append("visible_objects")

		tool_options = reordered

		if st.session_state.get("selected_tool") not in tool_options and tool_options:
			st.session_state["selected_tool"] = tool_options[0]

		selected_name = st.selectbox(
			"Tool",
			tool_options,
			format_func=lambda name: next(
				f"{tool['name']}  -  {tool['short_description']}"
				for tool in st.session_state["tools"]
				if tool["name"] == name
			),
			help="Pick any MCP tool to call manually.",
			key="selected_tool",
		)

		if selected_name in {"object_position", "object_detail"}:
			st.text_input(
				"Object name",
				key="object_name",
				value=st.session_state.get("object_name", "Moon"),
			)

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
		st.markdown('<div class="card-heading">Chatbot</div>', unsafe_allow_html=True)

		chat_ready = st.session_state.get("connection_state") == "connected" and st.session_state.get("bootstrap_ready")

		for msg in st.session_state["chat_messages"]:
			with st.chat_message(msg["role"]):
				st.markdown(msg["content"])

		if not st.session_state.get("started"):
			_render_center_notice("Connect to MCP server to load and use Chatbot.", "info")
			return

		if not chat_ready:
			_render_center_notice("Connect to MCP server to load and use Chatbot.", "info")
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

				try:
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
				except Exception as exc:
					assistant_text = f"Chatbot error: {exc}"
					assistant_placeholder.error(assistant_text)

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


def _render_header():
		# Intro hero card (text only)
		with st.container(border=False):
				st.markdown(
						"""
						<div class="hero">
							<div class="app-kicker">MCP Astronomy Assistant</div>
							<h1 class="app-title">StarGuide MCP Client</h1>
							<p class="app-summary">
								Connect to your StarGuide MCP server, call astronomy tools manually,
								and chat with an assistant that can use live sky, object, and weather data.
							</p>
							<div class="header-meta">
								<span>Location-aware</span>
								<span>Manual tools</span>
								<span>Tool-using chatbot</span>
							</div>
						</div>
						""",
						unsafe_allow_html=True,
				)

		# Separate image card below the hero
		image_path = Path(__file__).with_name("image.png")
		with image_path.open("rb") as img_file:
			image_data = img_file.read()
		base64_image = base64.b64encode(image_data).decode("utf-8")
		image_src = f"data:image/png;base64,{base64_image}"
		with st.container(border=False):
			st.markdown(
				f'<div class="image-card"><img src="{image_src}" style="width:100%; height:auto; border-radius:8px; display:block;"/></div>',
				unsafe_allow_html=True,
			)


def main():
	st.set_page_config(page_title="StarGuide MCP Client", page_icon="🔭", layout="wide")
	_init_state()
	_poll_connection()
	st.markdown(
		"""
		<style>
		.stApp {
			background: #f7faf9;
		}
		.block-container {
			padding-top: 5rem;
			padding-bottom: 2.5rem;
			max-width: 1600px; /* increased to allow wider hero */
		}

		
		.hero {
    background:

        radial-gradient(
            circle at 0% 0%,
            rgba(168,85,247,0.28),
            transparent 35%
        ),

        radial-gradient(
            circle at 100% 0%,
            rgba(99,102,241,0.25),
            transparent 35%
        ),

        radial-gradient(
            circle at 50% 100%,
            rgba(236,72,153,0.18),
            transparent 40%
        ),

        linear-gradient(
            135deg,
            #f5f3ff 0%,
            #ede9fe 25%,
            #e0e7ff 55%,
            #ddd6fe 80%,
            #f3e8ff 100%
        );

    padding: 4rem 5rem;

    border-radius: 24px;

    border: 1px solid rgba(139,92,246,0.18);

    box-shadow:
        0 20px 50px rgba(99,102,241,0.12);

    margin: 2rem auto;

    max-width: 1500px;

    text-align: center;

    overflow: hidden;
}



		.image-card {
			background: #0b1220; /* dark gray-black background */
			padding: 12px;
			border-radius: 12px;
			border: 1px solid rgba(203, 213, 225, 0.06);
			max-width: 1500px;
			margin: 0 auto 1.5rem auto;
			box-sizing: border-box;
		}

		.app-kicker {
			color: #047857;
			font-size: 0.95rem;
			font-weight: 700;
			letter-spacing: 0.08em;
			text-transform: uppercase;
			margin-bottom: 0.6rem;
		}
		.app-title {
			color: #10201b;
			font-size: clamp(3rem, 6vw, 5.6rem);
			line-height: 1.02;
			font-weight: 800;
			margin: 0 0 0.6rem 0;
			letter-spacing: 0;
		}
		.app-summary {
			color: #475569;
			font-size: 1.36rem;
			line-height: 1.5;
			max-width: 1100px;
			margin: 0 0 1rem 0;
		}

		.header-meta {
			display: flex;
			flex-wrap: wrap;
			gap: 0.5rem;
			justify-content: center;
		}
		.header-meta span {
			border: 1px solid rgba(4, 120, 87, 0.18);
			background: #ecfdf5;
			color: #065f46;
			border-radius: 999px;
			padding: 0.34rem 0.62rem;
			font-size: 0.82rem;
			font-weight: 650;
		}
.card-heading {
    background: linear-gradient(
        90deg,
        #7c3aed,
        #3b82f6
    );

    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;

    font-size: 1.15rem;

    font-weight: 800;

    margin-bottom: 0.25rem;
}

.card-heading::after {
    content: "";

    display: block;

    width: 60px;

    height: 3px;

    margin-top: 8px;

    border-radius: 999px;

    background: linear-gradient(
        90deg,
        #7c3aed,
        #3b82f6
    );
}
		div[data-testid="stButton"] button[kind="primary"] {
			background: #059669;
			border-color: #059669;
			color: white;
			font-weight: 700;
		}
		div[data-testid="stButton"] button[kind="primary"]:hover {
			background: #047857;
			border-color: #047857;
			color: white;
		}
		div[data-testid="stButton"] button:not([kind="primary"]) {
			border-color: rgba(148, 163, 184, 0.35);
			background: #111827;
			color: #d1fae5;
			font-weight: 700;
		}
		div[data-testid="stButton"] button:not([kind="primary"]):hover {
			border-color: rgba(96, 165, 250, 0.75);
			color: #ecfccb;
			background: #1f2937;
		}
	 

	
		.center-notice {
			width: 100%;
			text-align: center;
			border-radius: 8px;
			padding: 0.62rem 0.8rem;
			margin: 0.58rem 0;
			font-weight: 650;
			font-size: 0.92rem;
			border: 1px solid transparent;
		}
		.center-notice.success {
			background: #ecfdf5;
			border-color: #a7f3d0;
			color: #065f46;
		}
		.center-notice.info {
			background: #f0f9ff;
			border-color: #bae6fd;
			color: #075985;
		}
		.center-notice.error {
			background: #fef2f2;
			border-color: #fecaca;
			color: #991b1b;
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

	_render_header()

	input_col, manual_col = st.columns([1, 1.25], gap="large")
	with input_col:
		_render_input_card()
	with manual_col:
		_render_manual_tool_card()

	_render_chat_card()


if __name__ == "__main__":
	main()
