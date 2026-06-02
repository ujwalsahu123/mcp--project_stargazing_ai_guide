import asyncio
import json

import streamlit as st

from client import (
	auto_fetch_location,
	call_tool,
	current_iso_time,
	start_chatbot_bootstrap,
	stream_llm_chat_turn,
)


def _init_state():
	st.session_state.setdefault("lat", 0.0)
	st.session_state.setdefault("lon", 0.0)
	st.session_state.setdefault("alti", 0.0)
	st.session_state.setdefault("started", False)
	st.session_state.setdefault("tools", [])
	st.session_state.setdefault("last_result", None)
	st.session_state.setdefault("geo_message", "")
	st.session_state.setdefault("geo_error", "")
	st.session_state.setdefault("chat_messages", [])
	st.session_state.setdefault("llm_with_tools", None)
	st.session_state.setdefault("bootstrap_future", None)
	st.session_state.setdefault("bootstrap_error", "")
	st.session_state.setdefault("bootstrap_ready", False)
	st.session_state.setdefault("manual_output_nonce", 0)
	st.session_state.setdefault("manual_output_text", "")


def _load_tools_once():
	return


def _build_tool_args(tool_name):
	# Use latest current time at call-time for time-aware tools.
	latest_time = current_iso_time()

	lat = float(st.session_state["lat"])
	lon = float(st.session_state["lon"])
	alti = float(st.session_state.get("alti") or 0.0)

	if tool_name == "health_check":
		return {}
	if tool_name == "visible_objects":
		return {"lat": lat, "lon": lon, "time": latest_time, "alti": alti}
	if tool_name == "object_position":
		object_name = st.session_state.get("object_name", "Sun")
		return {
			"object_name": object_name,
			"lat": lat,
			"lon": lon,
			"time": latest_time,
			"alti": alti,
		}
	if tool_name == "object_detail":
		object_name = st.session_state.get("object_name", "Sun")
		return {"object_name": object_name}
	if tool_name == "weather_forecast":
		return {"lat": lat, "lon": lon}

	# Fallback for unknown tool names.
	return {"lat": lat, "lon": lon, "time": latest_time, "alti": alti}


def _on_auto_fetch_location():
	geo = auto_fetch_location()
	if geo.get("error"):
		st.session_state["geo_error"] = f"Could not auto-fetch location: {geo['error']}"
		st.session_state["geo_message"] = ""
		return

	if geo.get("latitude") is not None:
		st.session_state["lat"] = float(geo["latitude"])
	if geo.get("longitude") is not None:
		st.session_state["lon"] = float(geo["longitude"])

	place = ", ".join([p for p in [geo.get("city"), geo.get("country")] if p])
	st.session_state["geo_message"] = f"Location filled from IP lookup{': ' + place if place else ''}."
	st.session_state["geo_error"] = ""


def _on_start():
	st.session_state["bootstrap_future"] = start_chatbot_bootstrap(
		lat=float(st.session_state["lat"]),
		lon=float(st.session_state["lon"]),
		alti=float(st.session_state.get("alti") or 0.0),
	)
	st.session_state["llm_with_tools"] = None
	st.session_state["chat_messages"] = [{"role": "assistant", "content": "Loading visible objects..."}]
	st.session_state["started"] = True
	st.session_state["geo_error"] = ""
	st.session_state["bootstrap_error"] = ""
	st.session_state["bootstrap_ready"] = False
	st.session_state["tools"] = []
	st.session_state["last_result"] = None
	st.session_state["manual_output_text"] = ""
	st.session_state["manual_output_nonce"] = 0


def _poll_bootstrap():
	future = st.session_state.get("bootstrap_future")
	if not future:
		return
	if not future.done():
		return

	try:
		init_data = future.result()
	except Exception as exc:
		st.session_state["bootstrap_error"] = str(exc)
		st.session_state["bootstrap_future"] = None
		st.session_state["started"] = False
		return

	if init_data.get("error"):
		st.session_state["bootstrap_error"] = init_data["error"]
		st.session_state["bootstrap_future"] = None
		st.session_state["started"] = False
		return

	st.session_state["llm_with_tools"] = init_data.get("llm_with_tools")
	st.session_state["chat_messages"] = [{"role": "assistant", "content": init_data.get("intro_message", "How can I help you?")}]
	st.session_state["tools"] = init_data.get("tools_info", [])
	st.session_state["bootstrap_ready"] = True
	st.session_state["bootstrap_future"] = None


def main():
	st.set_page_config(page_title="StarGuide MCP Client", page_icon="*", layout="centered")
	_init_state()
	_poll_bootstrap()

	st.title("StarGuide MCP Tool Caller")
	st.caption("Set location, start session, call tools, and chat with the astronomy assistant.")

	if not st.session_state["started"]:
		with st.container(border=True):
			st.subheader("Location & Session Inputs")

			c1, c2 = st.columns(2)
			with c1:
				st.number_input("Latitude", key="lat", format="%.6f")
			with c2:
				st.number_input("Longitude", key="lon", format="%.6f")

			st.number_input("Altitude (meters, optional)", key="alti", format="%.2f")

			st.button("Auto Fetch Location", use_container_width=True, on_click=_on_auto_fetch_location)
			st.button("Start", type="primary", use_container_width=True, on_click=_on_start)

			if st.session_state["geo_error"]:
				st.error(st.session_state["geo_error"])
			if st.session_state["geo_message"]:
				st.success(st.session_state["geo_message"])

		st.info("Enter location details and click Start.")
		return

	if st.session_state.get("bootstrap_future") and not st.session_state.get("bootstrap_ready"):
		if hasattr(st, "autorefresh"):
			st.autorefresh(interval=1000, key="bootstrap_refresh")

	left_col, right_col = st.columns([1, 2], gap="large")

	with left_col:
		with st.container(border=True):
			st.subheader("Manual Tool Call")

			if not st.session_state["tools"]:
				st.info("Loading tools...")
			else:
				selected_tool = st.selectbox(
					"Select tool",
					st.session_state["tools"],
					key="selected_tool",
					format_func=lambda t: f"{t['name']} ({t['short_description']})",
				)
				tool_name = selected_tool["name"]

				if tool_name in {"object_position", "object_detail"}:
					st.text_input("Object name", key="object_name", value="Sun")

				if st.button("Call", use_container_width=True, disabled=not st.session_state["bootstrap_ready"]):
					args = _build_tool_args(tool_name)
					result = asyncio.run(call_tool(tool_name, args))
					st.session_state["last_result"] = {
						"tool": tool_name,
						"args": args,
						"result": result,
					}
					st.session_state["manual_output_text"] = json.dumps(st.session_state["last_result"], indent=2, default=str)
					st.session_state["manual_output_nonce"] += 1

			if st.session_state["manual_output_text"]:
				st.markdown("### Output")
				st.text_area(
					"",
					value=st.session_state["manual_output_text"],
					height=320,
					label_visibility="collapsed",
					key=f"manual_output_{st.session_state['manual_output_nonce']}",
					disabled=True,
				)

	with right_col:
		with st.container(border=True):
			st.subheader("Chatbot")

			if st.session_state.get("bootstrap_future") and not st.session_state.get("bootstrap_ready"):
				st.info("Loading visible objects...")

			for msg in st.session_state["chat_messages"]:
				with st.chat_message(msg["role"], avatar="😀" if msg["role"] == "user" else None):
					st.markdown(msg["content"])

			user_text = st.chat_input("Ask astronomy question...", key="chat_input_main")
			if user_text:
				with st.chat_message("user", avatar="😀"):
					st.markdown(user_text)

					assistant_placeholder = st.empty()

					def _render_delta(text):
						assistant_placeholder.markdown(text)

					with st.spinner("Thinking..."):
						assistant_text = asyncio.run(
							stream_llm_chat_turn(
								user_prompt=user_text,
								lat=float(st.session_state["lat"]),
								lon=float(st.session_state["lon"]),
								alti=float(st.session_state.get("alti") or 0.0),
								chat_messages=st.session_state["chat_messages"],
								llm_with_tools=st.session_state["llm_with_tools"],
								on_delta=_render_delta,
							)
						)
					assistant_placeholder.markdown(assistant_text)

				st.session_state["chat_messages"].append({"role": "user", "content": user_text})
				st.session_state["chat_messages"].append({"role": "assistant", "content": assistant_text})


if __name__ == "__main__":
	main()
