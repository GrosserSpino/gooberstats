import json, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class SiteDataTests(unittest.TestCase):
    def test_month_archives(self):
        for month in ('2026-07','2026-08'):
            root=ROOT/'docs/data/months'/month
            data=json.loads((root/'biggest-winners.json').read_text(encoding='utf-8'))
            self.assertEqual(data['month'],month)
            self.assertEqual(len(data['players']),50)
            self.assertEqual(len(list((root/'monthly-profiles').glob('*.json'))),50)
        august=json.loads((ROOT/'docs/data/months/2026-08/biggest-winners.json').read_text(encoding='utf-8'))
        self.assertEqual(august['players'][0]['name'],'Davi cardoso')
        self.assertEqual(august['players'][0]['wins'],415)
    def test_biggest_winners(self):
        data=json.loads((ROOT/'docs/data/biggest-winners.json').read_text(encoding='utf-8'))
        self.assertEqual(data['month'],'2026-08')
        self.assertEqual(len(data['players']),50)
        self.assertEqual(data['players'][0]['name'],'Davi cardoso')
        self.assertEqual(data['players'][0]['wins'],415)
        self.assertEqual([p['rank'] for p in data['players']],list(range(1,51)))
        self.assertIn('performanceRate',data['players'][0])
        self.assertIn('alltime',data['players'][0])
    def test_monthly_profile_links(self):
        data=json.loads((ROOT/'docs/data/biggest-winners.json').read_text(encoding='utf-8'))
        self.assertEqual(len(data['players']),50)
        self.assertTrue(data['top50Windows'])
        self.assertLess(data['performanceScaleMin'],data['performanceScaleMax'])
        total_profile_games=0
        for p in data['players']:
            profile=json.loads((ROOT/'docs/data/monthly-profiles'/f"{p['id']}.json").read_text(encoding='utf-8'))
            self.assertEqual(profile['month'],'2026-08')
            self.assertEqual(profile['games'],p['games'])
            self.assertEqual(len(profile['hourly']),24)
            self.assertLessEqual(profile['performanceGames'],profile['games'])
            self.assertEqual(profile['sourceTimeZone'],'Europe/Berlin')
            self.assertTrue(profile['coverageWindows'])
            self.assertEqual(sum(w['games'] for w in profile['hourlyWindows']),profile['performanceGames'])
            self.assertGreaterEqual(profile['activityScaleMax'],25)
            self.assertEqual(profile['performanceScaleMin'],data['performanceScaleMin'])
            self.assertEqual(profile['performanceScaleMax'],data['performanceScaleMax'])
            self.assertEqual((profile['difficultyScaleMin'],profile['difficultyScaleMax']),(-30,30))
            total_profile_games+=profile['performanceGames']
        self.assertEqual(sum(w['games'] for w in data['top50Windows']),total_profile_games)
        self.assertGreaterEqual(data['performanceScaleMax'],data['performanceScaleMin']+40)
    def test_activity_uses_scanner_coverage_not_active_days(self):
        profile=json.loads((ROOT/'docs/data/monthly-profiles'/'ef0f1623-66b8-4e57-9f0a-08b104875b7e.json').read_text(encoding='utf-8'))
        for row in profile['hourly']:
            expected=row['games']/row['coveredDays'] if row['coveredDays'] else 0
            self.assertAlmostEqual(row['gamesPerCoveredDay'],expected,places=3)
    def test_badges_are_finalized_months_only(self):
        badges=json.loads((ROOT/'docs/data/badges.json').read_text(encoding='utf-8'))
        self.assertTrue(badges)
        self.assertTrue(all(badge['month']<'2026-08' for rows in badges.values() for badge in rows))
        self.assertTrue(all({'month','monthLabel','rank','wins'}<=badge.keys() for rows in badges.values() for badge in rows))
if __name__=='__main__': unittest.main()
