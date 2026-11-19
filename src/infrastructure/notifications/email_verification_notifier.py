"""``EmailVerificationNotifierProtocol`` implementations.

- ``LoggingEmailVerificationNotifier``: writes the link to the log (dev/test).
- ``BrevoEmailVerificationNotifier``: sends through Brevo's HTTP API (Render's free tier
  blocks the usual mail ports).

Both take their content from ``_verification_message`` / ``_password_reset_message`` /
``_review_message``. Every email is bilingual (Vietnamese first, then English) and multipart:
``(subject, text, html)``. Preview the HTML locally with
``uv run python -m src.infrastructure.notifications.email_verification_notifier <outdir>``.
"""

from __future__ import annotations

import html as _html
import sys
from pathlib import Path

import httpx

from src.infrastructure.logging import configure_logging

_log = configure_logging()
_BREVO_URL = "https://api.brevo.com/v3/smtp/email"
_FONT = "Inter, -apple-system, 'Segoe UI', Roboto, Arial, sans-serif"
_REVIEW_BUTTON = ("Quản lý nhà hàng", "Manage restaurant")
_REVIEW_FOOTER = (
    "Bạn nhận được email này vì bạn là chủ nhà hàng trên FoodFen.",
    "You received this email because you own a restaurant on FoodFen.",
)


def _verification_link(base_url: str, token: str) -> str:
    return f"{base_url.rstrip('/')}/auth/verify-email?token={token}"


def _password_reset_link(base_url: str, token: str) -> str:
    return f"{base_url.rstrip('/')}/auth/reset-password?token={token}"


def _render_text(vi: list[str], en: list[str], link: str) -> str:
    def half(paragraphs: list[str]) -> str:
        return "\n\n".join([*paragraphs, link])

    return f"{half(vi)}\n\n{'—' * 24}\n\n{half(en)}\n"


def _render_html(
    preheader: str,
    heading_vi: str,
    vi: list[str],
    heading_en: str,
    en: list[str],
    button_vi: str,
    button_en: str,
    link: str,
    footer_vi: str,
    footer_en: str,
) -> str:
    # Callers pass plain strings; everything is escaped here so user-supplied values
    # (names, restaurant/dish names, rejection reasons) can never inject markup.
    e = _html.escape
    href = e(link, quote=True)

    def section(heading: str, paragraphs: list[str]) -> str:
        ps = "".join(
            f'<p style="margin:0 0 12px;font-size:16px;line-height:24px;color:#374151;">{e(p)}</p>'
            for p in paragraphs
        )
        return (
            f'<h1 style="margin:0 0 16px;font-size:22px;line-height:28px;font-weight:700;'
            f'color:#111827;">{e(heading)}</h1>{ps}'
        )

    def row(inner: str, style: str = "") -> str:
        return f'<tr><td style="{style}">{inner}</td></tr>'

    def cta(label: str) -> str:
        return (
            '<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>'
            '<td bgcolor="#15803D" style="border-radius:10px;background:#15803D;">'
            f'<a href="{href}" style="display:inline-block;padding:14px 28px;color:#FFFFFF;'
            "font-size:16px;font-weight:600;text-decoration:none;border-radius:10px;"
            f'font-family:{_FONT};">{e(label)}</a></td></tr></table>'
        )

    fallback = (
        '<p style="margin:0;font-size:13px;line-height:20px;color:#6B7280;">'
        "Nếu nút không hoạt động, hãy mở liên kết này · If the button doesn't work, open this link:"
        f'<br><a href="{href}" style="color:#15803D;word-break:break-all;">{href}</a></p>'
    )
    footer = (
        '<p style="margin:0;font-size:12px;line-height:18px;color:#6B7280;">'
        f"{e(footer_vi)}<br>{e(footer_en)}<br>© FoodFen</p>"
    )
    card = "".join(
        [
            row(
                '<span style="font-size:22px;font-weight:700;color:#15803D;">FoodFen</span>',
                "padding-bottom:24px;",
            ),
            row(section(heading_vi, vi)),
            row(cta(button_vi), "padding:12px 0 24px;"),
            row("", "border-top:1px solid #E5E7EB;font-size:0;line-height:0;height:1px;padding-bottom:24px;"),
            row(section(heading_en, en)),
            row(cta(button_en), "padding:12px 0 24px;"),
            row(fallback, "padding-bottom:24px;"),
            row(footer),
        ]
    )
    return (
        '<!doctype html><html lang="vi"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1"></head>'
        f'<body style="margin:0;padding:0;background:#F9FAFB;font-family:{_FONT};">'
        '<div style="display:none;max-height:0;overflow:hidden;opacity:0;mso-hide:all;">'
        f"{e(preheader)}</div>"
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        'bgcolor="#F9FAFB" style="background:#F9FAFB;"><tr>'
        '<td align="center" style="padding:32px 16px;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        'style="max-width:560px;background:#FFFFFF;border:1px solid #E5E7EB;border-radius:16px;">'
        '<tr><td style="padding:32px;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">{card}</table>'
        "</td></tr></table></td></tr></table></body></html>"
    )


def _compose(
    subject: str,
    preheader: str,
    heading_vi: str,
    vi: list[str],
    heading_en: str,
    en: list[str],
    button_vi: str,
    button_en: str,
    footer_vi: str,
    footer_en: str,
    link: str,
) -> tuple[str, str, str]:
    return (
        subject,
        _render_text(vi, en, link),
        _render_html(preheader, heading_vi, vi, heading_en, en, button_vi, button_en, link, footer_vi, footer_en),
    )


def _verification_message(name: str | None, link: str) -> tuple[str, str, str]:
    return _compose(
        "Xác nhận email FoodFen · Confirm your FoodFen email",
        "Xác nhận email để kích hoạt tài khoản FoodFen · Confirm your email to activate your FoodFen account",
        "Xác nhận email của bạn",
        [
            f"Chào {name}," if name else "Chào bạn,",
            "Hãy xác nhận địa chỉ email để kích hoạt tài khoản FoodFen của bạn.",
            "Liên kết sẽ hết hạn sau 24 giờ. Nếu bạn không tạo tài khoản, hãy bỏ qua email này.",
        ],
        "Confirm your email",
        [
            f"Hi {name}," if name else "Hi there,",
            "Confirm your email address to activate your FoodFen account.",
            "The link expires in 24 hours. If you didn't create an account, ignore this email.",
        ],
        "Xác nhận email",
        "Confirm email",
        "Bạn nhận được email này vì địa chỉ này vừa được dùng để đăng ký tài khoản FoodFen.",
        "You received this email because this address was used to sign up for FoodFen.",
        link,
    )


def _password_reset_message(name: str | None, link: str) -> tuple[str, str, str]:
    return _compose(
        "Đặt lại mật khẩu FoodFen · Reset your FoodFen password",
        "Liên kết đặt lại mật khẩu FoodFen của bạn · Your FoodFen password reset link",
        "Đặt lại mật khẩu",
        [
            f"Chào {name}," if name else "Chào bạn,",
            "Nhấn nút bên dưới để đặt lại mật khẩu FoodFen của bạn.",
            "Liên kết sẽ sớm hết hạn. Nếu bạn không yêu cầu, hãy bỏ qua email này — "
            "mật khẩu của bạn sẽ không thay đổi.",
        ],
        "Reset your password",
        [
            f"Hi {name}," if name else "Hi there,",
            "Use the button below to reset your FoodFen password.",
            "The link expires soon. If you didn't request this, ignore this email — "
            "your password will not change.",
        ],
        "Đặt lại mật khẩu",
        "Reset password",
        "Bạn nhận được email này vì có yêu cầu đặt lại mật khẩu cho tài khoản FoodFen dùng địa chỉ này.",
        "You received this email because a password reset was requested for the FoodFen account "
        "using this address.",
        link,
    )


def _owner_portal_link(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/restaurant"


def _review_message(
    name: str | None,
    restaurant_name: str,
    approved: bool,
    reason: str | None,
    dish_name: str | None,
    link: str,
) -> tuple[str, str, str]:
    r, d = restaurant_name, dish_name
    hi_vi = f"Chào {name}," if name else "Chào bạn,"
    hi_en = f"Hi {name}," if name else "Hi there,"
    why_vi = [f"Lý do: {reason}"] if reason else []
    why_en = [f"Reason: {reason}"] if reason else []
    if approved:
        subject = f"{r} đã được duyệt trên FoodFen · {r} is approved on FoodFen"
        preheader = f"{r} đã hiển thị với thực khách · {r} is now visible to diners"
        heading_vi = "Nhà hàng đã được duyệt"
        vi = [hi_vi, f"Tin vui: {r} đã được duyệt và đang hiển thị với thực khách.", "Quản lý nhà hàng của bạn tại đây."]
        heading_en = "Your restaurant is approved"
        en = [hi_en, f"Good news: {r} is approved and now visible to diners.", "Manage your restaurant here."]
    elif d:
        subject = f"Món {d} tại {r} chưa được duyệt · {d} at {r} was not approved"
        preheader = "Xem lý do và chỉnh sửa món ăn · See why and edit the dish"
        heading_vi = "Món ăn chưa được duyệt"
        vi = [
            hi_vi,
            f"Món {d} tại {r} chưa được duyệt nên thực khách chưa thể thấy.",
            *why_vi,
            "Hãy chỉnh sửa món ăn để gửi duyệt lại.",
        ]
        heading_en = "Dish not approved"
        en = [
            hi_en,
            f"Your dish {d} at {r} was not approved, so diners cannot see it.",
            *why_en,
            "Edit the dish to send it back for review.",
        ]
    else:
        subject = f"{r} chưa được duyệt trên FoodFen · {r} was not approved on FoodFen"
        preheader = "Xem lý do và cập nhật nhà hàng · See why and update your restaurant"
        heading_vi = "Nhà hàng chưa được duyệt"
        vi = [
            hi_vi,
            f"{r} chưa được duyệt nên thực khách chưa thể thấy.",
            *why_vi,
            "Hãy cập nhật nhà hàng để gửi duyệt lại.",
        ]
        heading_en = "Restaurant not approved"
        en = [
            hi_en,
            f"{r} was not approved, so diners cannot see it.",
            *why_en,
            "Update your restaurant to send it back for review.",
        ]
    return _compose(
        subject, preheader, heading_vi, vi, heading_en, en, *_REVIEW_BUTTON, *_REVIEW_FOOTER, link
    )


class LoggingEmailVerificationNotifier:
    def __init__(self, *, base_url: str) -> None:
        self._base_url = base_url

    async def send_verification(self, email: str, name: str | None, token: str) -> None:
        _log.info(
            "[email:console] verification link for %s -> %s",
            email,
            _verification_link(self._base_url, token),
        )

    async def send_password_reset(self, email: str, name: str | None, token: str) -> None:
        _log.info(
            "[email:console] password reset link for %s -> %s",
            email,
            _password_reset_link(self._base_url, token),
        )

    async def send_review_result(
        self,
        email: str,
        name: str | None,
        restaurant_name: str,
        approved: bool,
        reason: str | None,
        dish_name: str | None = None,
    ) -> None:
        link = _owner_portal_link(self._base_url)
        subject, _, _ = _review_message(name, restaurant_name, approved, reason, dish_name, link)
        _log.info("[email:console] review result for %s -> %s -> %s", email, subject, link)


class BrevoEmailVerificationNotifier:
    def __init__(self, *, base_url: str, sender: str, api_key: str, http: httpx.AsyncClient) -> None:
        self._base_url = base_url
        self._sender = sender
        self._api_key = api_key
        self._http = http

    async def send_verification(self, email: str, name: str | None, token: str) -> None:
        subject, text, html = _verification_message(name, _verification_link(self._base_url, token))
        await self._send(email, subject, text, html)

    async def send_password_reset(self, email: str, name: str | None, token: str) -> None:
        subject, text, html = _password_reset_message(name, _password_reset_link(self._base_url, token))
        await self._send(email, subject, text, html)

    async def send_review_result(
        self,
        email: str,
        name: str | None,
        restaurant_name: str,
        approved: bool,
        reason: str | None,
        dish_name: str | None = None,
    ) -> None:
        subject, text, html = _review_message(
            name, restaurant_name, approved, reason, dish_name, _owner_portal_link(self._base_url)
        )
        await self._send(email, subject, text, html)

    async def _send(self, email: str, subject: str, text: str, html: str) -> None:
        # Runs as a background task after the response: a failed email must be logged, not raised
        # (nobody awaits it, and it would only produce a noisy server error after a 200).
        try:
            response = await self._http.post(
                _BREVO_URL,
                headers={"api-key": self._api_key, "accept": "application/json"},
                json={
                    "sender": {"name": "FoodFen", "email": self._sender},
                    "to": [{"email": email}],
                    "subject": subject,
                    "textContent": text,
                    "htmlContent": html,
                },
                timeout=10,
            )
        except Exception:
            _log.exception("email delivery to %s failed", email)
            return
        if not response.is_success:
            _log.error(
                "email delivery to %s failed: %s %s", email, response.status_code, response.text
            )


if __name__ == "__main__":
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    base, rest, why = "https://foodfen.example", "Quán Ngon <b>& Co</b>", "Ảnh món ăn bị mờ · Photo is blurry"
    for fname, msg in {
        "verification": _verification_message("Ann", f"{base}/auth/verify-email?token=abc&x=1"),
        "password-reset": _password_reset_message("Ann", f"{base}/auth/reset-password?token=abc"),
        "restaurant-approved": _review_message("Ann", rest, True, None, None, f"{base}/restaurant"),
        "dish-rejected": _review_message("Ann", rest, False, why, "Phở bò", f"{base}/restaurant"),
        "restaurant-rejected": _review_message("Ann", rest, False, why, None, f"{base}/restaurant"),
    }.items():
        (out / f"{fname}.html").write_text(msg[2], encoding="utf-8")
        print(out / f"{fname}.html")
