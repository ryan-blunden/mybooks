from django_components import Component, register


class Alert(Component):
    def get_context_data(self, *args, **kwargs):
        title, classes = kwargs.get("title", ""), kwargs.get("classes", "")
        return {"title": title, "classes": classes}


@register("AlertInfo")
class AlertInfo(Alert):
    template_file = "info.html"


@register("AlertWarning")
class AlertWarning(Alert):
    template_file = "warning.html"


@register("AlertError")
class AlertError(Alert):
    template_file = "error.html"


@register("AlertSuccess")
class AlertSuccess(Alert):
    template_file = "success.html"
