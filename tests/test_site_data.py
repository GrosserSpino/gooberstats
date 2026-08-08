import json, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class SiteDataTests(unittest.TestCase):
    def test_biggest_winners(self):
        data=json.loads((ROOT/'docs/data/biggest-winners.json').read_text(encoding='utf-8'))
        self.assertEqual(data['month'],'2026-07')
        self.assertEqual(len(data['players']),50)
        self.assertEqual(data['players'][0]['name'],'Siegfried')
        self.assertEqual(data['players'][0]['wins'],709)
        self.assertEqual([p['rank'] for p in data['players']],list(range(1,51)))
    def test_profile_links(self):
        data=json.loads((ROOT/'docs/data/players.json').read_text(encoding='utf-8'))
        for p in data['leaderboard'][:100]: self.assertTrue((ROOT/'docs/data/profiles'/f"{p['id']}.json").exists())
if __name__=='__main__': unittest.main()
