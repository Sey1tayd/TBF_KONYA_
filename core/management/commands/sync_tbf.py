"""
TBF API'den Konya liglerinin mac programini ceker ve veritabanina kaydeder.
Kullanim: python manage.py sync_tbf
"""
import json
import subprocess
import requests
from datetime import datetime
from urllib.parse import urlencode
from django.core.management.base import BaseCommand
from django.conf import settings
from core.models import League, Team, Venue, Match


class Command(BaseCommand):
    help = 'TBF API\'den Konya lig maclarini senkronize eder'

    def _safe_write(self, msg, is_error=False):
        """Windows cp1252 encoding sorunlarini onler."""
        try:
            if is_error:
                self.stderr.write(msg)
            else:
                self.stdout.write(msg)
        except UnicodeEncodeError:
            safe_msg = msg.encode('ascii', 'replace').decode('ascii')
            if is_error:
                self.stderr.write(safe_msg)
            else:
                self.stdout.write(safe_msg)

    def add_arguments(self, parser):
        parser.add_argument(
            '--league-id',
            type=int,
            help='Sadece belirli bir ligi senkronize et (TBF faaliyetId)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Oynanan maclari da guncelle',
        )

    def handle(self, *args, **options):
        self.api_base = settings.TBF_API_BASE
        self.upstream_base = 'https://miniappapi.tbf.org.tr/webapi-service'
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8',
            'Referer': 'https://www.tbf.org.tr/',
            'Origin': 'https://www.tbf.org.tr',
        })

        if options['league_id']:
            leagues_data = [{'faaliyetId': options['league_id']}]
            # Lig bilgisini API'den al
            self.sync_single_league(options['league_id'], options['force'])
        else:
            self.sync_all_leagues(options['force'])

    def _api_get(self, path, params=None):
        """API'den veri cek - requests dene, basarisiz olursa curl kullan."""
        url = f"{self.api_base}/{path}"
        if params:
            url += '?' + urlencode(params)

        # Once requests ile dene
        try:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            pass

        # Cloudflare engeliyorsa curl ile dene
        try:
            result = subprocess.run(
                ['curl', '-s', url,
                 '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                 '-H', 'Accept: application/json; charset=utf-8',
                 '-H', 'Referer: https://www.tbf.org.tr/'],
                capture_output=True, timeout=30
            )
            if result.returncode == 0 and result.stdout.strip():
                return json.loads(result.stdout.decode('utf-8'))
        except Exception:
            pass

        return None

    # Bilinen Konya ligleri (2025-2026 sezonu)
    KNOWN_LEAGUES = [
        {'faaliyetId': 21615, 'faaliyetAdi': 'Necati YEGENOGLU Buyuk Erkekler Ligi', 'yasGrubu': 'Buyukler', 'cinsiyet': 'Erkek', 'seasonId': 172},
        {'faaliyetId': 21616, 'faaliyetAdi': 'Konya Buyuk Kadinlar', 'yasGrubu': 'Buyukler', 'cinsiyet': 'Kadin', 'seasonId': 172},
        {'faaliyetId': 21617, 'faaliyetAdi': 'Konya U10 Erkekler', 'yasGrubu': 'U10', 'cinsiyet': 'Erkek', 'seasonId': 172},
        {'faaliyetId': 21618, 'faaliyetAdi': 'Konya U10 Kizlar', 'yasGrubu': 'U10', 'cinsiyet': 'Kadin', 'seasonId': 172},
        {'faaliyetId': 21619, 'faaliyetAdi': 'Konya U11 Erkekler', 'yasGrubu': 'U11', 'cinsiyet': 'Erkek', 'seasonId': 172},
        {'faaliyetId': 21620, 'faaliyetAdi': 'Konya U11 Kizlar', 'yasGrubu': 'U11', 'cinsiyet': 'Kadin', 'seasonId': 172},
        {'faaliyetId': 21621, 'faaliyetAdi': 'Konya U12 Erkekler', 'yasGrubu': 'U12', 'cinsiyet': 'Erkek', 'seasonId': 172},
        {'faaliyetId': 21622, 'faaliyetAdi': 'Konya U12 Kizlar', 'yasGrubu': 'U12', 'cinsiyet': 'Kadin', 'seasonId': 172},
        {'faaliyetId': 21623, 'faaliyetAdi': 'Bahattin CANBILEN U14 Erkekler Ligi', 'yasGrubu': 'U14', 'cinsiyet': 'Erkek', 'seasonId': 172},
        {'faaliyetId': 21624, 'faaliyetAdi': 'Konya U14 Kizlar', 'yasGrubu': 'U14', 'cinsiyet': 'Kadin', 'seasonId': 172},
        {'faaliyetId': 21625, 'faaliyetAdi': 'Ismail ORGE U16 Erkekler Ligi', 'yasGrubu': 'U16', 'cinsiyet': 'Erkek', 'seasonId': 172},
        {'faaliyetId': 21626, 'faaliyetAdi': 'Konya U16 Kizlar', 'yasGrubu': 'U16', 'cinsiyet': 'Kadin', 'seasonId': 172},
        {'faaliyetId': 21627, 'faaliyetAdi': 'Mustafa SELCUK U18 Erkekler Ligi', 'yasGrubu': 'U18', 'cinsiyet': 'Erkek', 'seasonId': 172},
        {'faaliyetId': 21628, 'faaliyetAdi': 'Konya U18 Kizlar', 'yasGrubu': 'U18', 'cinsiyet': 'Kadin', 'seasonId': 172},
        {'faaliyetId': 21629, 'faaliyetAdi': 'Konya Umit Erkekler', 'yasGrubu': 'Umitler', 'cinsiyet': 'Erkek', 'seasonId': 172},
        {'faaliyetId': 21630, 'faaliyetAdi': 'Konya Umit Kadinlar', 'yasGrubu': 'Umitler', 'cinsiyet': 'Kadin', 'seasonId': 172},
    ]

    def sync_all_leagues(self, force=False):
        self._safe_write('Konya ligleri cekiliyor...')

        # Oncelikle API'den dene
        data = self._api_get('Altyapilar/filters-results', {
            'CityNameForLocalLeague': settings.TBF_CITY,
            'Season': settings.TBF_SEASON,
            'Page': 1,
            'PageSize': 50,
        })

        if data:
            leagues = data if isinstance(data, list) else data.get('data', data.get('items', []))
        else:
            self._safe_write('API erisilemedi, bilinen ligler kullaniliyor...')
            leagues = self.KNOWN_LEAGUES

        self._safe_write(f'{len(leagues)} lig bulundu.')

        for league_data in leagues:
            faaliyet_id = league_data.get('faaliyetId')
            if not faaliyet_id:
                continue

            league, created = League.objects.update_or_create(
                tbf_id=faaliyet_id,
                defaults={
                    'name': league_data.get('faaliyetAdi', ''),
                    'age_group': league_data.get('yasGrubu', ''),
                    'gender': league_data.get('cinsiyet', ''),
                    'season': league_data.get('sezonAdi', settings.TBF_SEASON),
                    'season_id': league_data.get('seasonId'),
                }
            )
            action = 'Eklendi' if created else 'Guncellendi'
            self._safe_write(f'  {action}: {league.name}')

            self.sync_league_matches(league, force)

    def sync_single_league(self, faaliyet_id, force=False):
        info = self._api_get('League/get-league-info', {'leagueId': faaliyet_id})
        data = {}
        if info:
            data = info.get('data', info) if isinstance(info, dict) else {}

        league, _ = League.objects.update_or_create(
            tbf_id=faaliyet_id,
            defaults={
                'name': data.get('faaliyetAdi', f'Lig {faaliyet_id}'),
                'age_group': data.get('yasGrubu', ''),
                'gender': data.get('cinsiyet', ''),
            }
        )
        self.sync_league_matches(league, force)

    def sync_league_matches(self, league, force=False):
        self._safe_write(f'  Haftalar cekiliyor: {league.name}...')

        params = {'leagueId': league.tbf_id}
        if league.season_id:
            params['seasonId'] = league.season_id

        weeks_data = self._api_get('League/get-league-weeks', params)
        if not weeks_data:
            self._safe_write(f'  Haftalar cekilemedi: {league.name}', is_error=True)
            return

        weeks = weeks_data if isinstance(weeks_data, list) else weeks_data.get('data', [])

        for week_info in weeks:
            week_num = week_info.get('sezon_Hafta')
            half_value = week_info.get('devre_Deger', '')
            display_text = week_info.get('display_Text', f'{week_num}. Hafta')

            if week_num is None:
                continue

            self.sync_week_matches(league, week_num, half_value, display_text, force)

    def sync_week_matches(self, league, week_num, half_value, display_text, force=False):
        params = {
            'ActivityId': league.tbf_id,
            'WeekFilter': week_num,
            'Page': 1,
            'PageSize': -1,
        }
        if half_value:
            params['HalfValue'] = half_value

        match_data = self._api_get('Match/get-all-matches-for-filter', params)
        if not match_data:
            return

        matches = match_data if isinstance(match_data, list) else match_data.get('data', match_data.get('items', []))

        if not matches:
            return

        created_count = 0
        updated_count = 0

        for m in matches:
            match_id = m.get('matchId')
            if not match_id:
                continue

            # Skor bilgisi
            home_team_data = m.get('homeTeam', {})
            away_team_data = m.get('awayTeam', {})
            home_score_str = home_team_data.get('score', '')
            away_score_str = away_team_data.get('score', '')
            home_score = int(home_score_str) if home_score_str and home_score_str.isdigit() else None
            away_score = int(away_score_str) if away_score_str and away_score_str.isdigit() else None
            is_played = home_score is not None and away_score is not None

            # Oynanan maclari atla (force degilse)
            if not force:
                existing = Match.objects.filter(tbf_match_id=match_id, is_played=True).first()
                if existing:
                    continue

            # Salon
            salon_name = m.get('salonAdi', '')
            venue = None
            if salon_name:
                venue, _ = Venue.objects.get_or_create(name=salon_name)

            # Takim
            home_team_name = home_team_data.get('name', '')
            away_team_name = away_team_data.get('name', '')

            # Takim nesnelerini bul/olustur
            home_team = None
            away_team = None
            if home_team_data.get('id'):
                home_team, _ = Team.objects.update_or_create(
                    tbf_id=home_team_data['id'],
                    defaults={
                        'name': home_team_name,
                        'league': league,
                        'logo_url': home_team_data.get('logoUrl', ''),
                    }
                )
            if away_team_data.get('id'):
                away_team, _ = Team.objects.update_or_create(
                    tbf_id=away_team_data['id'],
                    defaults={
                        'name': away_team_name,
                        'league': league,
                        'logo_url': away_team_data.get('logoUrl', ''),
                    }
                )

            # Tarih parse
            match_date_str = m.get('matchDateOnly', '')
            match_time_str = m.get('matchTime', '00:00')
            try:
                match_date = datetime.strptime(match_date_str, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                continue
            try:
                match_time = datetime.strptime(match_time_str, '%H:%M').time()
            except (ValueError, TypeError):
                match_time = datetime.strptime('00:00', '%H:%M').time()

            # Round/tur bilgisi - halfValue'dan
            round_info = ''
            devre_id = None
            for w in (m.get('week', ''),):
                pass
            half_val = m.get('halfValue', '')
            status_id = m.get('matchStatusId')

            _, created = Match.objects.update_or_create(
                tbf_match_id=match_id,
                defaults={
                    'match_code': m.get('matchCode', ''),
                    'league': league,
                    'home_team_name': home_team_name,
                    'away_team_name': away_team_name,
                    'home_team': home_team,
                    'away_team': away_team,
                    'venue': venue,
                    'date': match_date,
                    'time': match_time,
                    'week': m.get('week', display_text),
                    'round_info': round_info,
                    'home_score': home_score,
                    'away_score': away_score,
                    'is_played': is_played,
                    'match_status_id': status_id,
                }
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

        if created_count or updated_count:
            self._safe_write(
                f'    {display_text}: {created_count} yeni, {updated_count} guncellendi'
            )
