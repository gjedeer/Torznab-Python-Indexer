from base import Base
import json
import time
import re
import requests
import threading
import urllib
from collections import deque

class EventPollThread(threading.Thread):
    def __init__(self, event_queue, url, stop_event):
        self.queue = event_queue
        self.url = url
        self.stop_event = stop_event
        threading.Thread.__init__(self)

    def run(self):
        while not self.stop_event.is_set():
            r = requests.get(self.url % "/events", stream=True)
            if r.encoding is None:
                r.encoding = 'utf-8'

            for line in r.iter_lines(decode_unicode=True, chunk_size=2048):
                if line:
                    event = json.loads(line)
                    self.queue.append(event)

                if self.stop_event.is_set():
                    break

class Tribler(Base):
    """
    Asks a local Tribler instance.
    Run Tribler headless with twistd -n tribler before using this
    """
    url = 'http://localhost:8085%s'

    def __init__(self):
        self.queue = deque(maxlen=1000)
        self.stop_event = threading.Event()
        self.poll_thread = EventPollThread(self.queue, self.url, self.stop_event)
        self.poll_thread.start()

    def get_new_shows(self):
        items = self.get_items(self.new_shows_qs, self.elem_path)
        return self.parse_results(items)

    def get_search(self, phrase):
        # Send the search request
        requests.get(self.url % "/search?q=" + urllib.quote(phrase))
        
        rv = []
        # Consume the event queue for up to X seconds
        queue_start = time.time()
        while time.time() - queue_start < 5:
            try:
                event = self.queue.popleft()
            except IndexError:
                time.sleep(0.5)
                continue

            if event['type'] != 'search_result_torrent':
                continue
            if event['event']['query'].lower() != phrase.lower():
                print "Dropping %s - phrase" % event['event']['result']['name']
                continue

            result = event['event']['result']
            if result['relevance_score'] < 10:
                print "Dropping %s - score %.2f" % (result['name'], result['relevance_score'])
                continue

#            if result['num_seeders'] + result['num_leechers'] == 0:
#                print "Dropping %s - no seeds" % result['name']
#                continue

            print type(result['name'])
            magnet = "magnet:?xt=urn:btih:%s&dn=%s%s" %(
                result['infohash'],
                urllib.quote(result['name']),
                "&tr=udp%3A%2F%2Ftracker.leechers-paradise.org%3A6969&tr=udp%3A%2F%2Fzer0day.ch%3A1337&tr=udp%3A%2F%2Fopen.demonii.com%3A1337&tr=udp%3A%2F%2Ftracker.coppersurfer.tk%3A6969&tr=udp%3A%2F%2Fexodus.desync.com%3A6969",
            )
            
            rv.append({
                'title': result['name'],
                'permlink': 'tribler_fake_url://?id=%d&hash=%s' % (result['id'], result['infohash']),
                'magnet': magnet,
                'seeders': result['num_seeders'],
                'peers': result['num_leechers'],
                'size': result['size']
            })

        return rv

    def handle_request(self, request):
        q = request.GET.get('q')
        if q:
            #   doing regular query, where 'q' is the search phrase
            search_query = q
            if request.GET.get('season'):
                search_query += ' S' + request.GET.get('season').zfill(2)
                if request.GET.get('ep'):
                    search_query += 'E' + request.GET.get('ep').zfill(2)
            elements = self.get_search(search_query)
        else:
            if not request.GET.get('rid'):
                #   we need to handle query without params 'q' and 'rid'
                #   it is required by Sonarr test and for RSS checks
                elements = self.get_new_shows()
            else:
                #   it's important to return empty list if query is via 'rid' as we don't support it
                #   Sonarr will do another request, this time with string query 'q'
                elements = []

        return elements

    def stop(self):
        print "Sending stop event..."
        self.stop_event.set()
        print "Sending fake search request..."
        requests.get(self.url % "/search?q=stop")
        print "Joining..."
        self.poll_thread.join()

if __name__ == '__main__':
    try:
        tribler = Tribler()
        res = tribler.get_search('Archer s01e02')
        tribler.stop()
        print res
    except KeyboardInterrupt:
        print "Got the fucking ctrl-c"
        tribler.stop()
        raise

