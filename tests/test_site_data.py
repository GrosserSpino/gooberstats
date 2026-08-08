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
            self.assertEqual(profile['sourceTimeZone'],'Europe/Berlin')
            self.assertTrue(profile['coverageWindows'])
            self.assertEqual(sum(w['games'] for w in profile['hourlyWindows']),profile['performanceGames'])
    def test_activity_uses_scanner_coverage_not_active_days(self):
        profile=json.loads((ROOT/'docs/data/monthly-profiles'/'ef0f1623-66b8-4e57-9f0a-08b104875b7e.json').read_text(encoding='utf-8'))
        hour10=profile['hourly'][10]; hour23=profile['hourly'][23]
        self.assertEqual((hour10['games'],hour10['coveredDays']), (24,25))
        self.assertEqual((hour23['games'],hour23['coveredDays']), (148,26))
        self.assertAlmostEqual(hour10['gamesPerCoveredDay'],0.96,places=3)
        self.assertAlmostEqual(hour23['gamesPerCoveredDay'],5.692,places=3)
        self.assertGreater(hour23['gamesPerCoveredDay'],hour10['gamesPerCoveredDay'])
if __name__=='__main__': unittest.main()
