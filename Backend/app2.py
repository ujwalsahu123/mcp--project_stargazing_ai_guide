import asyncio
import html
import json
import re

import streamlit as st
import streamlit.components.v1 as components

from client2 import auto_fetch_location, current_iso_time, fetch_tools_info, start_health_check_bootstrap


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
	components.html(
		f"""
		<!DOCTYPE html>
		<html>
		<head>
		<style>
			html, body {{
				margin: 0;
				padding: 0;
				background: transparent;
				font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
			}}
			.box {{
				max-height: 320px;
				overflow: auto;
				border: 1px solid rgba(49, 51, 63, 0.18);
				border-radius: 10px;
				background: #fff;
				padding: 12px 14px;
				box-sizing: border-box;
			}}
			pre {{
				margin: 0;
				white-space: pre;
				line-height: 1.45;
				font-size: 0.92rem;
			}}
			.json-key {{ color: #7c3aed; }}
			.json-string {{ color: #15803d; }}
			.json-number {{ color: #1d4ed8; }}
			.json-bool {{ color: #b45309; }}
			.json-null {{ color: #dc2626; }}
		</style>
		</head>
		<body>
			<div class="box"><pre>{_json_html(value)}</pre></div>
		</body>
		</html>
		""",
		height=340,
		scrolling=False,
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
	st.session_state.setdefault("object_name", "Sun")
	st.session_state.setdefault("last_result", None)
	st.session_state.setdefault(
		"output_text",
		json.dumps({"output": None, "message": "Call the tool for output..."}, indent=2),
	)


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
	st.session_state["connect_future"] = start_health_check_bootstrap()
	st.session_state["started"] = True
	st.session_state["tools"] = []
	st.session_state["last_result"] = None
	st.session_state["output_text"] = json.dumps(
		{"output": None, "message": "Call the tool for output..."},
		indent=2,
	)


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
		st.session_state["connection_error"] = "MCP server error."
		st.session_state["connect_future"] = None
		return

	st.session_state["connection_state"] = "connected"
	st.session_state["connection_message"] = "MCP server connected."
	st.session_state["connection_error"] = ""
	st.session_state["connect_future"] = None

	if not st.session_state["tools"]:
		st.session_state["tools"] = asyncio.run(fetch_tools_info())
		if not st.session_state["selected_tool"] and st.session_state["tools"]:
			st.session_state["selected_tool"] = st.session_state["tools"][0]["name"]


@st.fragment(run_every=1)
def _connection_status_fragment():
	future = st.session_state.get("connect_future")
	if not st.session_state.get("started"):
		return

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
	from client2 import call_tool

	return await call_tool(tool_name, args)


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
		</style>
		""",
		unsafe_allow_html=True,
	)

	st.title("StarGuide MCP Client")
	st.caption("Enter your location, connect to the MCP server, then call tools manually.")

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

	with st.container(border=True):
		st.subheader("Manual Tool Call")

		if st.session_state["connection_state"] == "connected":
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
		else:
			st.info("Connect to MCP server to load and use tools.")


if __name__ == "__main__":
	main()