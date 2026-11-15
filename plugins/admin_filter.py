"""Runtime admin filter so panel-managed admins work without a restart."""
from pyrogram import filters
import info


def _is_admin(_, __, update):
    user = getattr(update, "from_user", None)
    return bool(user and user.id in info.ADMINS)


ADMIN_FILTER = filters.create(_is_admin, name="RuntimeAdminFilter")
