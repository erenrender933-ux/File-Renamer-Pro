# Very small in-memory state machine: maps user_id -> dict describing
# what the bot is waiting for next from that user (a filename, a caption
# template, a GoFile token, etc). Good enough for a single-process bot;
# swap for a Redis-backed store if you run multiple workers.

pending = {}


def set_pending(user_id, action, **data):
    pending[user_id] = {"action": action, **data}


def get_pending(user_id):
    return pending.get(user_id)


def clear_pending(user_id):
    pending.pop(user_id, None)
