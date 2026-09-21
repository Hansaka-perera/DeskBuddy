from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Callable, Optional

import requests

from .config import Settings, Personality


class Brain:
    def __init__(self, db, settings: Settings, personality: Personality, context_provider: Callable[[], dict]):
        self.db = db
        self.settings = settings
        self.personality = personality
        self.context_provider = context_provider
        self.last_emotion = "neutral"
        self.last_effect = "none"
        self.last_sound = "none"
        self.last_action = "normal"

    def respond(self, user_text: str) -> str:
        user_text = user_text.strip()
        if not user_text:
            return "I'm listening."

        self.db.add_message("user", user_text)
        self._extract_memory(user_text)

        local = self._local_answer(user_text)
        if local:
            response = local
        else:
            response = self._provider_answer(user_text)

        self.db.add_message("assistant", response)
        if self.last_emotion == "neutral":
            self.last_emotion = self._infer_emotion(user_text, response)
        return response

    def _local_answer(self, text: str) -> Optional[str]:
        t = text.lower().strip()
        now = datetime.now()
        if "what time" in t or t in {"time?", "time"}:
            return f"It's {now.strftime('%I:%M %p').lstrip('0')}."
        if "what are you doing" in t or "what are you doing?" in t or "what you doing" in t:
            return "I'm right here on your desktop, keeping an eye on things and waiting for you."
        if any(k in t for k in ["tell me a joke", "joke", "make me laugh"]):
            return "I tried to learn Python, but it kept asking me to indent my feelings. 😂"
        if "who are you" in t or "what are you" in t:
            return f"I'm {self.personality.name} — your tiny desktop companion."
        if t in {"hi", "hello", "hey", "hey buddy"}:
            return f"Hey! I'm {self.personality.name}. What's up?"
        if "good morning" in t:
            return "Good morning! Let's pretend we have a plan. 😄"
        if "good night" in t:
            return "Good night. Save your work before you disappear on me."
        return None

    def _provider_answer(self, user_text: str) -> str:
        provider = (self.settings.get("ai_provider") or os.getenv("AI_PROVIDER", "none")).lower()
        system = self._system_prompt()
        history = self.db.recent_messages(10)
        messages = [{"role": "system", "content": system}]
        for item in history:
            messages.append({"role": item["role"], "content": item["content"]})
        if provider == "openai":
            return self._openai(messages)
        if provider == "lmstudio":
            return self._lmstudio(messages)
        if provider == "ollama":
            return self._ollama(messages)
        return "My AI brain isn't connected yet. Set ai_provider to lmstudio, openai, or ollama in config/settings.json."

    def _system_prompt(self) -> str:
        p = self.personality.data
        memory = self.db.get_memory() if self.settings.get("memory_enabled", True) else []
        context = self.context_provider()
        memory_text = "\n".join(
            f"- {m['category']}.{m['memory_key']}: {m['memory_value']}" for m in memory[:20]
        ) or "No saved memories."
        return (
            p.get("system_prompt", "You are a friendly desktop companion.")
            + "\n\nCURRENT CONTEXT:\n"
            + json.dumps(context, ensure_ascii=False)
            + "\n\nMEMORY:\n"
            + memory_text
            + "\n\nReturn natural, concise replies for a tiny desktop companion. The Buddy never speaks aloud; replies are shown as text. Keep reply under about 140 characters when practical."
        )

    def _openai(self, messages: list) -> str:
        key = os.getenv("OPENAI_API_KEY", "").strip()
        if not key:
            return "Your OpenAI API key is missing. Put it in the project's .env file."
        base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com").rstrip("/")
        model = os.getenv("OPENAI_MODEL", "gpt-5-mini")
        try:
            r = requests.post(
                f"{base}/v1/responses",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": model, "input": messages},
                timeout=60,
            )
            r.raise_for_status()
            data = r.json()
            if data.get("output_text"):
                return str(data["output_text"]).strip()
            parts = []
            for item in data.get("output", []):
                for c in item.get("content", []):
                    if isinstance(c, dict) and c.get("text"):
                        parts.append(c["text"])
            return "\n".join(parts).strip() or "I got an empty AI response."
        except Exception as exc:
            return f"My AI connection hit a snag: {exc}"

    def _lmstudio(self, messages: list) -> str:
        """Talk to LM Studio's OpenAI-compatible local server and parse Buddy metadata."""
        base = (self.settings.get("lmstudio_base_url") or "http://127.0.0.1:1234/v1").rstrip("/")
        model = (self.settings.get("lmstudio_model") or "").strip()
        if not model or model == "YOUR-MODEL-ID":
            self.last_emotion, self.last_effect, self.last_sound = "neutral", "none", "error"
            return "LM Studio is selected, but lmstudio_model is not configured."

        url = f"{base}/chat/completions"
        request_messages = list(messages)
        request_messages[0] = {
            "role": "system",
            "content": request_messages[0]["content"] + "\n\nYou are Buddy, a small playful desktop robot. Return ONLY a valid JSON object: exactly reply, emotion, sound, action. Never use Markdown or code fences. emotion: neutral,happy,sad,angry,annoyed,surprised,confused,curious,sleepy,excited,bored,thinking,playful. sound: none,click,thinking,happy,surprised,confused,error,sleep,wake,reaction,notification. action: normal,sleep,wake,stay,move_left,move_right,wander,stop. Match emotion to reply tone. Keep reply under 140 characters."
        }
        payload = {
            "model": model,
            "messages": request_messages,
            "temperature": 0.7,
            "stream": False,
            "response_format": {"type": "text"}
        }
        headers = {"Content-Type": "application/json"}
        api_key = os.getenv("LMSTUDIO_API_KEY", "").strip()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            r = requests.post(url, headers=headers, json=payload, timeout=120)
            r.raise_for_status()
            data = r.json()
            choices = data.get("choices", [])
            if not choices:
                self.last_emotion, self.last_effect, self.last_sound = "neutral", "none", "error"
                return "LM Studio returned no choices."
            message = choices[0].get("message", {})
            content = message.get("content", "")
            if isinstance(content, list):
                content = "".join(str(part.get("text", "")) for part in content if isinstance(part, dict))
            content = str(content).strip()
            result = self._parse_buddy_json(content)
            if result:
                self.last_emotion = result["emotion"]
                self.last_effect = result["eye_effect"]
                self.last_sound = result["sound"]
                self.last_action = result["action"]
                return result["reply"]
            self.last_emotion, self.last_effect, self.last_sound, self.last_action = "thinking", "none", "thinking", "normal"
            return "Hmm... give me a second."
        except requests.exceptions.ConnectionError:
            self.last_emotion, self.last_effect, self.last_sound = "neutral", "none", "error"
            return "I can't reach LM Studio. Start the Local Server on 127.0.0.1:1234."
        except requests.exceptions.Timeout:
            self.last_emotion, self.last_effect, self.last_sound = "sleepy", "thinking", "error"
            return "LM Studio took too long to respond."
        except requests.exceptions.HTTPError as exc:
            detail = ""
            try:
                detail = f" — {r.text[:500]}"
            except Exception:
                pass
            self.last_emotion, self.last_effect, self.last_sound = "neutral", "none", "error"
            return f"LM Studio API error: {exc}{detail}"
        except Exception as exc:
            self.last_emotion, self.last_effect, self.last_sound = "neutral", "none", "error"
            return f"LM Studio connection error: {exc}"

    def _parse_buddy_json(self, content: str):
        try:
            cleaned = content
            if cleaned.startswith("```"):
                cleaned = cleaned.strip("`")
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
            data = json.loads(cleaned)
            reply = str(data.get("reply", "")).strip()
            if not reply:
                return None
            emotions = {"neutral","happy","sad","angry","annoyed","surprised","confused","curious","sleepy","excited","bored","thinking","playful","listening"}
            sounds = {"none","click","thinking","happy","surprised","confused","error","sleep","wake","reaction","notification"}
            actions = {"normal","sleep","wake","stay","move_left","move_right","wander","stop"}
            emotion = str(data.get("emotion", "neutral")).lower()
            sound = str(data.get("sound", "none")).lower()
            action = str(data.get("action", "normal")).lower()
            effect_by_emotion = {
                "happy": "none", "sad": "none", "angry": "none", "annoyed": "none",
                "surprised": "none", "confused": "confused", "curious": "none",
                "sleepy": "close", "thinking": "none", "listening": "none",
                "excited": "flicker", "playful": "none", "bored": "none",
            }
            return {
                "reply": reply,
                "emotion": emotion if emotion in emotions else "neutral",
                "eye_effect": effect_by_emotion.get(emotion, "none"),
                "sound": sound if sound in sounds else "none",
                "action": action if action in actions else "normal",
            }
        except Exception:
            return None

    def _ollama(self, messages: list) -> str:
        base = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
        model = os.getenv("OLLAMA_MODEL", "llama3.2")
        try:
            r = requests.post(
                f"{base}/api/chat",
                json={"model": model, "messages": messages, "stream": False},
                timeout=120,
            )
            r.raise_for_status()
            data = r.json()
            return str(data.get("message", {}).get("content", "No response."))
        except Exception as exc:
            return f"My local AI isn't responding: {exc}"

    def _extract_memory(self, text: str) -> None:
        if not self.settings.get("memory_enabled", True):
            return
        patterns = [
            (r"my favorite (game|movie|food|color|song) is (.+)", "favorite"),
            (r"i am learning (.+)", "learning"),
            (r"i'm learning (.+)", "learning"),
            (r"remember (?:that )?(.+)", "user_note"),
        ]
        for pattern, category in patterns:
            m = re.search(pattern, text, flags=re.I)
            if m:
                if category == "favorite":
                    key = f"favorite_{m.group(1).lower()}"
                    value = m.group(2).strip(" .")
                elif category == "learning":
                    key = "learning_topic"
                    value = m.group(1).strip(" .")
                else:
                    key = f"note_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    value = m.group(1).strip(" .")
                self.db.remember(category, key, value)
                break

    @staticmethod
    def _infer_emotion(user_text: str, response: str) -> str:
        t = user_text.lower()
        if any(x in t for x in ["haha", "😂", "joke", "funny"]):
            return "happy"
        if any(x in t for x in ["angry", "mad", "hate"]):
            return "concerned"
        if any(x in t for x in ["wow", "surprise", "really?!"]):
            return "surprised"
        if "?" in user_text:
            return "curious"
        return "neutral"
