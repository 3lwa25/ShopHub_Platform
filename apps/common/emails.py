from django.conf import settings
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags


def send_templated_email(subject, template_name, context, recipient_list, bcc=None, attachments=None, fail_silently=True):
    """Send HTML + text email based on template."""
    if not recipient_list:
        return

    context = dict(context or {})
    context.setdefault('support_email', getattr(settings, 'SUPPORT_EMAIL', getattr(settings, 'DEFAULT_FROM_EMAIL', 'support@shophub.com')))
    context.setdefault('site_url', getattr(settings, 'SITE_URL', 'http://localhost:8000'))
    if len(recipient_list) == 1:
        context.setdefault('recipient_email', recipient_list[0])
    else:
        context.setdefault('recipient_email', ', '.join(recipient_list))

    html_body = render_to_string(template_name, context)
    text_template = template_name.replace('.html', '.txt')
    try:
        text_body = render_to_string(text_template, context)
    except Exception:
        text_body = strip_tags(html_body)

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', settings.EMAIL_HOST_USER),
        to=recipient_list,
        bcc=bcc or [],
    )
    email.attach_alternative(html_body, "text/html")

    if attachments:
        for attachment in attachments:
            # attachment: tuple (filename, content, mimetype)
            if attachment and len(attachment) == 3:
                email.attach(*attachment)

    email.send(fail_silently=fail_silently)
