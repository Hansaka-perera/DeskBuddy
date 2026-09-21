# Desk Buddy — LM Studio + RoboEyes-style Desktop Edition

Desk Buddy is a small Windows desktop companion with a **184×120 always-on-top window**.

This edition intentionally does **not** use Text-to-Speech. Buddy communicates through:

**Text + Eye Animation + Short Sound Effects**

Sound effects are loaded directly from `assets/sounds` as MP3 files. Camera is
off by default and all camera processing stays local. Voice commands include
“stay here”, “move left/right”, “start moving”, “wake up”, and “set a sleep
alarm for 10 PM”.

The supplied **Robo Eyes Arduino Library** is included for reference under `third_party/RoboEyes/`.
The desktop version does not need Arduino or an OLED. `ui/roboeyes_engine.py` is a PySide6/QPainter adaptation of the RoboEyes-style mood/effect vocabulary.

## Features

- 184×120 borderless desktop companion
- Always-on-top
- Draggable
- LM Studio local AI
- Qwen 2.5 3B configuration by default
- SQLite memory
- Conversation history
- Microphone speech-to-text
- Optional camera
- Time awareness
- Idle/proactive behavior
- **No AI voice / no TTS**
- Short sound effects only
- RoboEyes-style moods and animations
- Response text displayed inside the Buddy window

## RoboEyes-style effects

- DEFAULT / NEUTRAL
- HAPPY
- TIRED / SLEEPY
- ANGRY
- BLINK
- AUTO BLINK
- IDLE MOVEMENT
- CONFUSED
- LAUGH
- HORIZONTAL FLICKER
- VERTICAL FLICKER
- CURIOSITY
- SWEAT
- OPEN / CLOSE
- Directional positions N, NE, E, SE, S, SW, W, NW

These concepts correspond to the public API/effect vocabulary visible in the supplied RoboEyes library.

## LM Studio

1. Start LM Studio.
2. Load your local model.
3. Start the Local Server on `127.0.0.1:1234`.
4. Keep `config/settings.json` configured as:

```json
"ai_provider": "lmstudio",
"lmstudio_base_url": "http://127.0.0.1:1234/v1",
"lmstudio_model": "qwen2.5-3b-instruct"
```

Use the exact model ID exposed by your LM Studio server.

## Install

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

## Interaction

- Left-drag: move Buddy
- Click: open Chat
- Double-click: open Chat
- Right-click: menu
- F8: push-to-talk

## AI response contract

LM Studio is asked for JSON like:

```json
{
  "reply": "Again? 😂",
  "emotion": "playful",
  "eye_effect": "laugh",
  "sound": "reaction",
  "action": "normal"
}
```

Buddy then:

1. Shows `reply` as text.
2. Sends `emotion` / `eye_effect` to the eye engine.
3. Plays the selected short sound effect.
4. Never speaks the response.

## Eye system

`ui/eyes_host.py` contains the visual host.

`ui/roboeyes_engine.py` is the desktop animation engine.

You can replace the renderer later with your own visual implementation while keeping the same public state methods such as:

```python
face.set_state("happy", "laugh")
face.set_state("curious", "curious")
face.set_state("sleepy", "blink")
```

## RoboEyes source

The original supplied RoboEyes source is preserved in:

```text
third_party/RoboEyes/
```

See its included `LICENSE.txt` before redistributing the bundled library separately.
