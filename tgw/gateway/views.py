from django.shortcuts import render
from providers import piratebay
from providers import tribler


class Endpoints:
    piratebay = 'tpb'
    tribler = 'tribler'


def index(request):
    if request.GET.get('t') == 'caps':
        return render(request, 'gateway/caps.html', {}, content_type='application/rss+xml')

    enabled_providers = {
        Endpoints.piratebay: piratebay.PirateBay(),
        Endpoints.tribler: tribler.Tribler(),
    }

    elements = []
    for provider in enabled_providers:
        if '/'+provider+'/' in request.path_info:
            elements = enabled_providers[provider].handle_request(request)
            break

    context = {
        'offset': 0,
        'total': len(elements),
        'items': elements
    }

    return render(request, 'gateway/index.html', context, content_type='application/rss+xml')

