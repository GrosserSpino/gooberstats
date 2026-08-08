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
    def test_monthly_profile_links(self):
        data=json.loads((ROOT/'docs/data/biggest-winners.json').read_text(encoding='utf-8'))
        self.assertEqual(len(data['players']),50)
        for p in data['players']:
            profile=json.loads((ROOT/'docs/data/monthly-profiles'/f"{p['id']}.json").read_text(encoding='utf-8'))
            self.assertEqual(profile['month'],'2026-07')
            self.assertEqual(profile['games'],p['games'])
            self.assertEqual(len(profile['hourly']),24)
            self.assertLessEqual(profile['performanceGames'],profile['games'])
if __name__=='__main__': unittest.main()
