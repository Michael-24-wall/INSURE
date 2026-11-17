from .channels import get_channels


def notify(user, title, message, category="system", link=""):
    if user is None:
        return None
    result = None
    for channel in get_channels():
        created = channel.send(user, title, message, category, link)
        if channel.name == "in_app":
            result = created
    return result


def notify_many(users, title, message, category="system", link=""):
    return [notify(u, title, message, category, link) for u in users if u]
