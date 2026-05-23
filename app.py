import os
import json
from flask import Flask, request, jsonify, send_from_directory, Response, stream_with_context
from openai import OpenAI

app = Flask(__name__, static_folder="static")

# ── Config ────────────────────────────────────────────────────────────────────
DEFAULT_MODEL   = os.getenv("OPENAI_MODEL", "gpt-4o")
DEFAULT_API_KEY = os.getenv("OPENAI_API_KEY", "")
SYSTEM_PROMPT   = """You are a helpful AI assistant running locally. You are knowledgeable, thoughtful, and friendly.
You can help with analysis, writing, coding, research, and general questions.
When you don't know something, say so. Keep responses clear and well-structured."""

# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/api/chat", methods=["POST"])
def chat():
    data       = request.json
    api_key    = data.get("api_key") or DEFAULT_API_KEY
    model      = data.get("model", DEFAULT_MODEL)
    messages   = data.get("messages", [])
    stream     = data.get("stream", True)
    sys_prompt = data.get("system_prompt", SYSTEM_PROMPT)

    if not api_key:
        return jsonify({"error": "No API key provided."}), 400
    if not messages:
        return jsonify({"error": "No messages provided."}), 400

    client = OpenAI(api_key=api_key)

    full_messages = [{"role": "system", "content": sys_prompt}] + messages

    if stream:
        def generate():
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=full_messages,
                    stream=True,
                    max_tokens=4096,
                )
                for chunk in resp:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        yield f"data: {json.dumps({'text': delta.content})}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        return Response(stream_with_context(generate()),
                        content_type="text/event-stream",
                        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
    else:
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=full_messages,
                max_tokens=4096,
            )
            return jsonify({"text": resp.choices[0].message.content,
                            "usage": resp.usage.model_dump()})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

@app.route("/api/models", methods=["POST"])
def list_models():
    data    = request.json
    api_key = data.get("api_key") or DEFAULT_API_KEY
    if not api_key:
        return jsonify({"error": "No API key"}), 400
    try:
        client = OpenAI(api_key=api_key)
        models = client.models.list()
        chat_models = sorted(
            [m.id for m in models.data if any(k in m.id for k in ["gpt-4", "gpt-3.5", "o1", "o3", "o4"])],
        )
        return jsonify({"models": chat_models})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    print("\n🤖  Local AI Chat is running!")
    print("    Open http://localhost:5000 in your browser\n")
    app.run(debug=False, port=5000)
