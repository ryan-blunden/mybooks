from django_components import Component, register


@register("Link")
class Link(Component):
    template_file = "link.html"

    def get_context_data(self, **kwargs):
        url = kwargs.pop("url", None)
        if url is None:
            raise ValueError("Link component requires a 'url' argument")
        target = kwargs.pop("target", "_self")

        return {"url": url, "target": target, "props": kwargs}
