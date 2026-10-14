import unittest
from monitor import parse_page, update_state


class MonitorTests(unittest.TestCase):
    def test_initial_scan_is_silent_then_deduplicates(self):
        first = {"1": {"id": "1", "title": "Winx"}}
        state = update_state({}, first)
        self.assertEqual(state["pending"], {})
        next_items = dict(first, **{"2": {"id": "2", "title": "Винкс"}})
        state = update_state(state, next_items)
        self.assertEqual(list(state["pending"]), ["2"])
        state["pending"].clear()
        self.assertEqual(update_state(state, next_items)["pending"], {})

    def test_pending_survives_next_scan(self):
        state = {"initialized": True, "seen": ["2"], "pending": {"2": {"id": "2"}}}
        self.assertIn("2", update_state(state, {})["pending"])

    def test_blocked_page_does_not_look_like_empty_results(self):
        with self.assertRaises(RuntimeError):
            parse_page('<html>Доступ ограничен</html>')

    def test_cards_keep_matches_in_description(self):
        document = '''<div data-marker="item" data-item-id="123"><a data-marker="item-title" href="/moskva/toys/winx_123">Кукла Winx</a><span data-marker="item-price">500 ₽</span></div><div data-marker="item" data-item-id="124"><a data-marker="item-title" href="/moskva/toys/other_124">Другая кукла</a></div>'''
        items, more = parse_page(document)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["price"], "500 ₽")
        self.assertFalse(more)


if __name__ == "__main__":
    unittest.main()
