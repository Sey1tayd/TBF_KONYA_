import json
from datetime import timedelta, date
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Q
from django.contrib import messages

from .models import UserProfile, League, Match, Availability, AvailabilityRequest, Assignment, AssignmentWindow, Tournament


def login_view(request):
    error = None
    if request.method == 'POST':
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('core:dashboard')
        else:
            error = 'Kullanici adi veya sifre hatali.'
    return render(request, 'core/login.html', {'error': error})


def logout_view(request):
    logout(request)
    return redirect('core:login')


def _get_profile(request):
    profile = getattr(request.user, 'profile', None)
    if not profile:
        profile = UserProfile.objects.create(user=request.user, role='hakem')
    return profile


def _is_admin(profile):
    return profile.role in ('atama_sorumlusu', 'il_temsilcisi')


def _is_official(profile):
    return profile.role in ('hakem', 'masa_gorevlisi', 'gozlemci')


@login_required
def dashboard(request):
    profile = _get_profile(request)

    if _is_admin(profile):
        return _admin_dashboard(request, profile)
    else:
        return _official_dashboard(request, profile)


def _admin_dashboard(request, profile):
    today = date.today()

    # Filtreler
    league_filter = request.GET.get('league', '')
    status_filter = request.GET.get('status', '')  # all, upcoming, played, unassigned

    # Hafta navigasyonu
    week_offset = int(request.GET.get('week', 0))
    week_start = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    week_end = week_start + timedelta(days=6)

    # Tum maclari cek (sadece bu haftanin)
    qs = Match.objects.filter(
        date__range=(week_start, week_end)
    ).select_related('league', 'tournament', 'venue').order_by('date', 'time')

    if league_filter:
        qs = qs.filter(league_id=league_filter)

    assigned_ids = set(Assignment.objects.values_list('match_id', flat=True))

    if status_filter == 'upcoming':
        qs = qs.filter(is_played=False)
    elif status_filter == 'played':
        qs = qs.filter(is_played=True)
    elif status_filter == 'unassigned':
        qs = qs.filter(is_played=False).exclude(id__in=assigned_ids)

    # Gunlere gore grupla
    from collections import defaultdict
    days_dict = defaultdict(list)
    for m in qs:
        days_dict[m.date].append(m)

    weeks_data = []
    current = week_start
    while current <= week_end:
        day_matches = days_dict.get(current, [])
        weeks_data.append({
            'date': current,
            'day_name': _turkish_day(current),
            'matches': day_matches,
            'match_count': len(day_matches),
            'is_today': current == today,
        })
        current += timedelta(days=1)

    # Ozet istatistikler (tum sezon)
    all_upcoming = Match.objects.filter(date__gte=today, is_played=False)
    unassigned_upcoming = all_upcoming.exclude(id__in=assigned_ids)

    officials = UserProfile.objects.filter(
        is_active_official=True, role__in=['hakem', 'masa_gorevlisi', 'gozlemci']
    )
    avail_users = Availability.objects.filter(
        date__range=(week_start, week_end)
    ).values_list('user_id', flat=True).distinct()

    leagues = League.objects.all().order_by('name')

    context = {
        'profile': profile,
        'total_upcoming': all_upcoming.count(),
        'unassigned_count': unassigned_upcoming.count(),
        'assigned_count': all_upcoming.count() - unassigned_upcoming.count(),
        'total_officials': officials.count(),
        'reported_officials': avail_users.count(),
        'week_start': week_start,
        'week_end': week_end,
        'week_offset': week_offset,
        'prev_week': week_offset - 1,
        'next_week': week_offset + 1,
        'weeks_data': weeks_data,
        'leagues': leagues,
        'league_filter': league_filter,
        'status_filter': status_filter,
        'assigned_ids': assigned_ids,
        'total_week_matches': qs.count(),
    }
    return render(request, 'core/admin_dashboard.html', context)


def _official_dashboard(request, profile):
    from collections import defaultdict
    today = date.today()

    # Benim atama q filtresi
    my_q = _get_my_q_filter(profile)
    my_match_ids = set(
        Match.objects.filter(my_q).values_list('id', flat=True)
    )

    # Hafta navigasyonu
    week_offset = int(request.GET.get('week', 0))
    week_start = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    week_end = week_start + timedelta(days=6)

    # Bu haftanin tum maclari
    all_week_matches = Match.objects.filter(
        date__range=(week_start, week_end)
    ).select_related('league', 'tournament', 'venue', 'assignment',
                     'assignment__head_referee__user',
                     'assignment__assistant_referee__user').order_by('date', 'time')

    # Gunlere gore grupla
    days_dict = defaultdict(list)
    for m in all_week_matches:
        days_dict[m.date].append(m)

    weeks_data = []
    current = week_start
    while current <= week_end:
        day_matches = days_dict.get(current, [])
        weeks_data.append({
            'date': current,
            'day_name': _turkish_day(current),
            'matches': day_matches,
            'match_count': len(day_matches),
            'is_today': current == today,
            'is_weekend': current.weekday() >= 5,
        })
        current += timedelta(days=1)

    # Musaitlik durumum
    active_request = AvailabilityRequest.objects.filter(
        is_active=True, target_roles__contains=profile.role
    ).first()
    if active_request:
        avail_range = (active_request.start_date, active_request.end_date)
    else:
        avail_range = (today, today + timedelta(days=13))

    my_availabilities = Availability.objects.filter(
        user=profile, date__range=avail_range
    ).order_by('date')
    reported_dates = set(my_availabilities.values_list('date', flat=True))
    avail_days = [avail_range[0] + timedelta(days=i)
                  for i in range((avail_range[1] - avail_range[0]).days + 1)]
    unreported = [d for d in avail_days if d not in reported_dates]

    # Yaklasan gorevlerim ozeti
    my_upcoming_count = Match.objects.filter(my_q, date__gte=today).count()

    context = {
        'profile': profile,
        'weeks_data': weeks_data,
        'my_match_ids': my_match_ids,
        'my_upcoming_count': my_upcoming_count,
        'week_start': week_start,
        'week_end': week_end,
        'week_offset': week_offset,
        'prev_week': week_offset - 1,
        'next_week': week_offset + 1,
        'week_total': all_week_matches.count(),
        'my_availabilities': my_availabilities,
        'unreported_days': len(unreported),
        'total_days': len(avail_days),
        'active_request': active_request,
    }
    return render(request, 'core/official_dashboard.html', context)


def _get_my_q_filter(profile):
    """Kullanicinin atamalarini bulan Q filtresi."""
    role_filters = {
        'hakem': Q(assignment__head_referee=profile) | Q(assignment__assistant_referee=profile),
        'masa_gorevlisi': (
            Q(assignment__scorer_1=profile) | Q(assignment__scorer_2=profile) |
            Q(assignment__timer=profile) | Q(assignment__shot_clock=profile)
        ),
        'gozlemci': Q(assignment__observer=profile),
    }
    return role_filters.get(profile.role, Q())


def _get_role_label(profile, assignment):
    """Atamada bu kullanicinin gorevi ne."""
    if not assignment:
        return ''
    if assignment.head_referee == profile:
        return 'Bas Hakem'
    if assignment.assistant_referee == profile:
        return 'Yardimci Hakem'
    if assignment.scorer_1 == profile or assignment.scorer_2 == profile:
        return 'Sayi Gorevlisi'
    if assignment.timer == profile:
        return 'Sure Gorevlisi'
    if assignment.shot_clock == profile:
        return 'Sut Saati Gorevlisi'
    if assignment.observer == profile:
        return 'Gozlemci'
    return ''


@login_required
def my_assignments(request):
    """Kullanicinin atanmis oldugu maclar."""
    profile = _get_profile(request)
    if not _is_official(profile):
        return redirect('core:dashboard')

    today = date.today()
    q_filter = _get_my_q_filter(profile)

    upcoming = Match.objects.filter(
        q_filter, date__gte=today
    ).select_related('league', 'venue', 'assignment',
                     'assignment__head_referee__user', 'assignment__assistant_referee__user',
                     'assignment__scorer_1__user', 'assignment__scorer_2__user',
                     'assignment__timer__user', 'assignment__shot_clock__user',
                     'assignment__observer__user').order_by('date', 'time')

    past = Match.objects.filter(
        q_filter, date__lt=today
    ).select_related('league', 'venue', 'assignment',
                     'assignment__head_referee__user', 'assignment__assistant_referee__user').order_by('-date', '-time')[:30]

    upcoming_data = []
    for m in upcoming:
        asgn = getattr(m, 'assignment', None)
        upcoming_data.append({
            'match': m,
            'assignment': asgn,
            'my_role': _get_role_label(profile, asgn),
            'day_name': _turkish_day(m.date),
        })

    past_data = []
    for m in past:
        asgn = getattr(m, 'assignment', None)
        past_data.append({
            'match': m,
            'assignment': asgn,
            'my_role': _get_role_label(profile, asgn),
            'day_name': _turkish_day(m.date),
        })

    context = {
        'profile': profile,
        'upcoming_data': upcoming_data,
        'past_data': past_data,
    }
    return render(request, 'core/my_assignments.html', context)


@login_required
def availability_view(request):
    profile = _get_profile(request)
    if not _is_official(profile):
        return redirect('core:dashboard')

    today = date.today()

    # Aktif istek var mi?
    active_request = AvailabilityRequest.objects.filter(
        is_active=True,
        target_roles__contains=profile.role
    ).first()

    if request.method == 'POST':
        dates_str = request.POST.getlist('dates[]')
        statuses = request.POST.getlist('statuses[]')
        notes = request.POST.getlist('notes[]')

        saved = 0
        for i, date_str in enumerate(dates_str):
            try:
                d = date.fromisoformat(date_str)
            except (ValueError, IndexError):
                continue

            status = statuses[i] if i < len(statuses) else 'available'
            note = notes[i] if i < len(notes) else ''

            Availability.objects.update_or_create(
                user=profile,
                date=d,
                defaults={
                    'is_available': status == 'available',
                    'note': note,
                }
            )
            saved += 1

        messages.success(request, f'{saved} gun icin musaitlik bildirildi.')
        return redirect('core:availability')

    # Aktif istek varsa onun tarihlerini goster, yoksa 14 gun
    if active_request:
        date_list = active_request.date_range
    else:
        date_list = [today + timedelta(days=i) for i in range(14)]

    days = []
    for d in date_list:
        existing = Availability.objects.filter(user=profile, date=d).first()
        match_count = Match.objects.filter(date=d, is_played=False).count()
        days.append({
            'date': d,
            'day_name': _turkish_day(d),
            'existing': existing,
            'match_count': match_count,
        })

    context = {
        'profile': profile,
        'days': days,
        'active_request': active_request,
    }
    return render(request, 'core/availability.html', context)


def _turkish_short_day(d):
    names = {0: 'Pzt', 1: 'Sal', 2: 'Car', 3: 'Per', 4: 'Cum', 5: 'Cmt', 6: 'Paz'}
    return names.get(d.weekday(), '')


@login_required
def availability_summary(request):
    """Atama sorumlusu: tum gorevlilerin musaitlik ozeti."""
    profile = _get_profile(request)
    if not _is_admin(profile):
        return redirect('core:dashboard')

    today = date.today()

    # Aktif istek varsa onun tarihlerini kullan
    active_request = AvailabilityRequest.objects.filter(is_active=True).first()

    start_str = request.GET.get('start_date')
    end_str = request.GET.get('end_date')

    if start_str:
        try:
            start_date = date.fromisoformat(start_str)
        except ValueError:
            start_date = None
    else:
        start_date = None

    if end_str:
        try:
            end_date = date.fromisoformat(end_str)
        except ValueError:
            end_date = None
    else:
        end_date = None

    # Varsayilan: aktif istek > bu hafta
    if not start_date:
        if active_request:
            start_date = active_request.start_date
        else:
            start_date = today - timedelta(days=today.weekday())
    if not end_date:
        if active_request:
            end_date = active_request.end_date
        else:
            end_date = start_date + timedelta(days=6)

    # Tarih listesi (zengin bilgiyle)
    date_range = []
    d = start_date
    while d <= end_date:
        date_range.append({
            'date': d,
            'short_name': _turkish_short_day(d),
            'weekday': d.weekday(),
            'is_today': d == today,
        })
        d += timedelta(days=1)

    # Gorevliler
    officials = UserProfile.objects.filter(
        is_active_official=True,
        role__in=['hakem', 'masa_gorevlisi', 'gozlemci']
    ).select_related('user').order_by('role', 'user__first_name')

    # Musaitlikleri tek sorguda cek
    availabilities = {}
    for avail in Availability.objects.filter(date__range=(start_date, end_date)):
        availabilities[(avail.user_id, avail.date)] = avail

    groups = [
        ('Hakemler', [o for o in officials if o.role == 'hakem']),
        ('Masa Gorevlileri', [o for o in officials if o.role == 'masa_gorevlisi']),
        ('Gozlemciler', [o for o in officials if o.role == 'gozlemci']),
    ]

    summary_groups = []
    for group_name, group_officials in groups:
        rows = []
        # Gun bazli sayaclar
        day_counts = [{'available': 0, 'total': len(group_officials)} for _ in date_range]

        for official in group_officials:
            day_statuses = []
            for idx, dr in enumerate(date_range):
                avail = availabilities.get((official.id, dr['date']))
                if avail:
                    status = 'musait' if avail.is_available else 'dolu'
                    note = avail.note
                    if avail.is_available:
                        day_counts[idx]['available'] += 1
                else:
                    status = 'belirtilmedi'
                    note = ''
                day_statuses.append({'date': dr['date'], 'status': status, 'note': note})
            rows.append({'official': official, 'days': day_statuses})

        summary_groups.append({
            'name': group_name,
            'rows': rows,
            'day_counts': day_counts,
        })

    context = {
        'summary_groups': summary_groups,
        'date_range': date_range,
        'col_count': len(date_range) + 1,
        'start_date': start_date,
        'end_date': end_date,
        'active_request': active_request,
    }
    return render(request, 'core/availability_summary.html', context)


@login_required
def availability_request_list(request):
    """Musaitlik istekleri listesi."""
    profile = _get_profile(request)
    if not _is_admin(profile):
        return redirect('core:dashboard')

    requests_list = AvailabilityRequest.objects.all()[:20]
    req_data = []
    for req in requests_list:
        responded, total = req.get_response_count()
        req_data.append({'request': req, 'responded': responded, 'total': total})

    context = {'req_data': req_data}
    return render(request, 'core/availability_request_list.html', context)


@login_required
def availability_request_create(request):
    """Yeni musaitlik istegi olustur."""
    profile = _get_profile(request)
    if not _is_admin(profile):
        return redirect('core:dashboard')

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        description = request.POST.get('description', '')
        target_roles = request.POST.getlist('target_roles')

        if not title or not start_date or not end_date:
            messages.error(request, 'Baslik ve tarihler zorunludur.')
            return redirect('core:availability_request_create')

        # Onceki aktif istekleri kapat
        AvailabilityRequest.objects.filter(is_active=True).update(is_active=False)

        AvailabilityRequest.objects.create(
            title=title,
            description=description,
            start_date=date.fromisoformat(start_date),
            end_date=date.fromisoformat(end_date),
            target_roles=','.join(target_roles) if target_roles else 'hakem,masa_gorevlisi,gozlemci',
            is_active=True,
            created_by=request.user,
        )
        messages.success(request, f'Musaitlik istegi olusturuldu: {title}')
        return redirect('core:availability_request_list')

    today = date.today()
    next_monday = today + timedelta(days=(7 - today.weekday()))
    next_sunday = next_monday + timedelta(days=6)

    context = {
        'default_start': next_monday,
        'default_end': next_sunday,
    }
    return render(request, 'core/availability_request_create.html', context)


@login_required
def availability_request_detail(request, pk):
    """Musaitlik istegi detayi."""
    profile = _get_profile(request)
    if not _is_admin(profile):
        return redirect('core:dashboard')

    try:
        avail_request = AvailabilityRequest.objects.get(pk=pk)
    except AvailabilityRequest.DoesNotExist:
        return redirect('core:availability_request_list')

    # Bu istege donen musaitlikleri goster
    return redirect(
        f"/musaitlik/ozet/?start_date={avail_request.start_date.isoformat()}&end_date={avail_request.end_date.isoformat()}"
    )


@login_required
def user_list(request):
    """Tum kullanicilarin listesi."""
    profile = _get_profile(request)
    if not _is_admin(profile):
        return redirect('core:dashboard')

    users = UserProfile.objects.filter(
        is_active_official=True
    ).select_related('user').order_by('role', 'user__first_name')

    groups = [
        ('Hakemler', [u for u in users if u.role == 'hakem']),
        ('Masa Gorevlileri', [u for u in users if u.role == 'masa_gorevlisi']),
        ('Gozlemciler', [u for u in users if u.role == 'gozlemci']),
        ('Il Temsilcileri', [u for u in users if u.role == 'il_temsilcisi']),
        ('Atama Sorumlulari', [u for u in users if u.role == 'atama_sorumlusu']),
    ]

    # Tum kullanicilar (admin dahil)
    all_users = UserProfile.objects.select_related('user').order_by('role', 'user__first_name')

    context = {
        'groups': groups,
        'all_users': all_users,
        'total': all_users.count(),
    }
    return render(request, 'core/user_list.html', context)


@login_required
def assignment_sheet(request):
    """Excel benzeri atama sayfasi - secilen gunlere gore."""
    profile = _get_profile(request)
    if not _is_admin(profile):
        return redirect('core:dashboard')

    today = date.today()
    league_id = request.GET.get('league', '')
    tournament_id = request.GET.get('tournament', '')

    # Secilen gunler: ?dates[]=2026-04-16&dates[]=2026-04-17 ...
    selected_dates_str = request.GET.getlist('dates[]')
    if not selected_dates_str:
        # Default: bu haftanin oynanmamis mac olan gunleri
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        selected_dates = list(
            Match.objects.filter(date__range=(week_start, week_end), is_played=False)
            .values_list('date', flat=True).distinct().order_by('date')
        )
    else:
        selected_dates = []
        for ds in selected_dates_str:
            try:
                selected_dates.append(date.fromisoformat(ds))
            except ValueError:
                pass
        selected_dates = sorted(set(selected_dates))

    if not selected_dates:
        matches = Match.objects.none()
    else:
        matches = Match.objects.filter(
            date__in=selected_dates,
            is_played=False,
        ).select_related('league', 'tournament', 'venue').order_by('date', 'time')

    if league_id:
        matches = matches.filter(league_id=league_id)

    if tournament_id:
        matches = matches.filter(tournament_id=tournament_id)

    match_data = []
    for match in matches:
        assignment = Assignment.objects.filter(match=match).select_related(
            'head_referee__user', 'assistant_referee__user',
            'scorer_1__user', 'scorer_2__user',
            'timer__user', 'shot_clock__user',
            'observer__user'
        ).first()
        match_data.append({
            'match': match,
            'assignment': assignment,
            'day_name': _turkish_day(match.date),
        })

    # Klasmana gore sirali hakemler: A > B > C > il > aday > belirsiz
    referees_qs = list(UserProfile.objects.filter(
        role='hakem', is_active_official=True
    ).select_related('user'))
    referees_qs.sort(key=lambda r: (r.classification_order, r.full_name))

    table_officials = list(UserProfile.objects.filter(
        role='masa_gorevlisi', is_active_official=True
    ).select_related('user').order_by('user__first_name', 'user__last_name'))

    observers = list(UserProfile.objects.filter(
        role='gozlemci', is_active_official=True
    ).select_related('user').order_by('user__first_name', 'user__last_name'))

    leagues = League.objects.filter(is_active=True).order_by('name')
    tournaments = Tournament.objects.filter(is_active=True).order_by('-start_date')

    # Musaitlik verisi (JSON) - secilen gunler icin
    availabilities = {}
    if selected_dates:
        for avail in Availability.objects.filter(date__in=selected_dates):
            key = f"{avail.user_id}_{avail.date.isoformat()}"
            availabilities[key] = avail.is_available

    # Takvimde gosterilecek mevcut mac gunleri (son 30 + sonraki 60 gun)
    calendar_start = today - timedelta(days=30)
    calendar_end = today + timedelta(days=60)
    match_dates = list(
        Match.objects.filter(date__range=(calendar_start, calendar_end), is_played=False)
        .values_list('date', flat=True).distinct().order_by('date')
    )

    # Atama penceresi - global veya turnuvaya ozgu
    from django.utils import timezone as tz
    now_tz = tz.now()
    if tournament_id:
        active_window = AssignmentWindow.objects.filter(
            is_active=True,
            start_datetime__lte=now_tz,
            end_datetime__gte=now_tz,
        ).filter(
            Q(tournament_id=tournament_id) | Q(tournament__isnull=True)
        ).first()
    else:
        active_window = AssignmentWindow.get_active()
    window_is_open = active_window is not None
    upcoming_window = AssignmentWindow.objects.filter(
        is_active=True, start_datetime__gt=now_tz,
    ).filter(
        Q(tournament_id=tournament_id) | Q(tournament__isnull=True)
        if tournament_id else Q(tournament__isnull=True)
    ).order_by('start_datetime').first()

    # Secili turnuva objesi
    selected_tournament_obj = None
    if tournament_id:
        selected_tournament_obj = Tournament.objects.filter(pk=tournament_id).first()

    context = {
        'match_data': match_data,
        'referees': referees_qs,
        'table_officials': table_officials,
        'observers': observers,
        'leagues': leagues,
        'tournaments': tournaments,
        'selected_dates': [d.isoformat() for d in selected_dates],
        'selected_league': league_id,
        'selected_tournament': tournament_id,
        'selected_tournament_obj': selected_tournament_obj,
        'availabilities_json': json.dumps(availabilities),
        'match_dates_json': json.dumps([d.isoformat() for d in match_dates]),
        'window_is_open': window_is_open,
        'active_window': active_window,
        'upcoming_window': upcoming_window,
    }
    return render(request, 'core/assignment_sheet.html', context)


@login_required
@require_POST
def assignment_save(request):
    """AJAX ile atama kaydetme."""
    profile = _get_profile(request)
    if not _is_admin(profile):
        return JsonResponse({'error': 'Yetkiniz yok'}, status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Gecersiz veri'}, status=400)

    match_id = data.get('match_id')
    field = data.get('field')
    user_id = data.get('user_id')

    valid_fields = ['head_referee', 'assistant_referee', 'scorer_1', 'scorer_2', 'timer', 'shot_clock', 'observer']
    if field not in valid_fields:
        return JsonResponse({'error': 'Gecersiz alan'}, status=400)

    try:
        match = Match.objects.select_related('tournament').get(id=match_id)
    except Match.DoesNotExist:
        return JsonResponse({'error': 'Mac bulunamadi'}, status=404)

    # Atama penceresi kontrolu - maca gore kontrol et
    if not AssignmentWindow.is_open_for_match(match):
        return JsonResponse({'error': 'Atama penceresi kapali. Simdi atama yapilamaz.'}, status=403)

    assignment, _ = Assignment.objects.get_or_create(
        match=match, defaults={'created_by': request.user}
    )

    user_name = ''
    if user_id:
        try:
            official = UserProfile.objects.get(id=user_id)
            user_name = official.full_name
        except UserProfile.DoesNotExist:
            return JsonResponse({'error': 'Gorevli bulunamadi'}, status=404)
        setattr(assignment, field, official)
    else:
        setattr(assignment, field, None)

    assignment.save()

    return JsonResponse({
        'success': True,
        'match_id': match_id,
        'field': field,
        'user_name': user_name,
    })


@login_required
def api_available_people(request):
    """Belirli bir tarih ve rol icin musait kisileri dondurur."""
    match_date = request.GET.get('date')
    role = request.GET.get('role', 'hakem')

    if not match_date:
        return JsonResponse({'people': []})

    try:
        match_date = date.fromisoformat(match_date)
    except ValueError:
        return JsonResponse({'people': []})

    role_map = {
        'hakem': ['hakem'],
        'masa': ['masa_gorevlisi'],
        'gozlemci': ['gozlemci'],
    }
    roles = role_map.get(role, ['hakem'])

    officials = UserProfile.objects.filter(
        role__in=roles, is_active_official=True
    ).select_related('user')

    people = []
    for official in officials:
        avail = Availability.objects.filter(user=official, date=match_date).first()
        people.append({
            'id': official.id,
            'name': official.full_name,
            'available': avail.is_available if avail else None,
        })

    return JsonResponse({'people': people})


@login_required
def api_week_matches(request):
    start = request.GET.get('start_date')
    end = request.GET.get('end_date')

    if not start or not end:
        return JsonResponse({'matches': []})

    try:
        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
    except ValueError:
        return JsonResponse({'matches': []})

    matches = Match.objects.filter(
        date__range=(start_date, end_date), is_played=False
    ).select_related('league', 'venue').order_by('date', 'time')

    result = []
    for m in matches:
        assignment = Assignment.objects.filter(match=m).first()
        result.append({
            'id': m.id,
            'date': m.date.isoformat(),
            'time': m.time.strftime('%H:%M'),
            'match_code': m.match_code,
            'league': m.league.name if m.league else '',
            'home_team': m.home_team_name,
            'away_team': m.away_team_name,
            'venue': m.venue.name if m.venue else '',
            'round_info': m.round_info,
        })

    return JsonResponse({'matches': result})


@login_required
def assignment_pdf_view(request):
    """Yazdirilabilir atama listesi."""
    profile = _get_profile(request)
    if not _is_admin(profile):
        return redirect('core:dashboard')

    today = date.today()
    selected_dates_str = request.GET.getlist('dates[]')
    if selected_dates_str:
        selected_dates = []
        for ds in selected_dates_str:
            try:
                selected_dates.append(date.fromisoformat(ds))
            except ValueError:
                pass
        selected_dates = sorted(set(selected_dates))
        matches = Match.objects.filter(date__in=selected_dates, is_played=False)
    else:
        # Fallback: bu hafta
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        matches = Match.objects.filter(date__range=(week_start, week_end), is_played=False)
        selected_dates = [week_start, week_end]

    matches = matches.select_related('league', 'venue').order_by('date', 'time')

    match_data = []
    for match in matches:
        assignment = Assignment.objects.filter(match=match).select_related(
            'head_referee__user', 'assistant_referee__user',
            'scorer_1__user', 'scorer_2__user',
            'timer__user', 'shot_clock__user',
            'observer__user'
        ).first()
        match_data.append({
            'match': match,
            'assignment': assignment,
            'day_name': _turkish_day(match.date),
        })

    context = {
        'match_data': match_data,
        'selected_dates': selected_dates,
        'today': today,
    }
    return render(request, 'core/assignment_pdf.html', context)


def _turkish_day(d):
    days = {
        0: 'Pazartesi', 1: 'Sali', 2: 'Carsamba',
        3: 'Persembe', 4: 'Cuma', 5: 'Cumartesi', 6: 'Pazar',
    }
    return days.get(d.weekday(), '')


# ─── Atama Penceresi Yonetimi ─────────────────────────────────────────────────

@login_required
def assignment_window_list(request):
    """Atama pencerelerini listele ve yonet."""
    profile = _get_profile(request)
    if not _is_admin(profile):
        return redirect('core:dashboard')

    from django.utils import timezone as tz
    windows = AssignmentWindow.objects.select_related('tournament').all().order_by('-created_at')
    active_window = AssignmentWindow.get_active()

    context = {
        'profile': profile,
        'windows': windows,
        'active_window': active_window,
        'now': tz.now(),
    }
    return render(request, 'core/assignment_window_list.html', context)


@login_required
def assignment_window_create(request):
    """Yeni atama penceresi olustur."""
    profile = _get_profile(request)
    if not _is_admin(profile):
        return redirect('core:dashboard')

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        start_str = request.POST.get('start_datetime', '')
        end_str = request.POST.get('end_datetime', '')
        note = request.POST.get('note', '')

        from django.utils import timezone as tz
        from datetime import datetime as dt

        if not title or not start_str or not end_str:
            messages.error(request, 'Tum alanlar zorunludur.')
            return redirect('core:assignment_window_create')

        try:
            # Tarayicidan gelen format: 2026-04-20T14:00
            start_dt = tz.make_aware(dt.fromisoformat(start_str))
            end_dt = tz.make_aware(dt.fromisoformat(end_str))
        except (ValueError, TypeError):
            messages.error(request, 'Gecersiz tarih formati.')
            return redirect('core:assignment_window_create')

        if start_dt >= end_dt:
            messages.error(request, 'Bitis zamani baslangictan sonra olmalidir.')
            return redirect('core:assignment_window_create')

        tournament_id = request.POST.get('tournament', '') or None

        AssignmentWindow.objects.create(
            title=title,
            start_datetime=start_dt,
            end_datetime=end_dt,
            note=note,
            is_active=True,
            created_by=request.user,
            tournament_id=tournament_id,
        )
        messages.success(request, f'Atama penceresi olusturuldu: {title}')
        return redirect('core:assignment_window_list')

    from django.utils import timezone as tz
    from datetime import datetime as dt
    now = tz.localtime(tz.now())
    default_start = now.strftime('%Y-%m-%dT%H:%M')
    default_end = (now + timedelta(hours=48)).strftime('%Y-%m-%dT%H:%M')

    context = {
        'profile': profile,
        'default_start': default_start,
        'default_end': default_end,
        'tournaments': Tournament.objects.filter(is_active=True).order_by('-start_date'),
    }
    return render(request, 'core/assignment_window_create.html', context)


@login_required
def assignment_window_toggle(request, pk):
    """Pencereyi aktif/pasif yap."""
    profile = _get_profile(request)
    if not _is_admin(profile):
        return redirect('core:dashboard')

    try:
        window = AssignmentWindow.objects.get(pk=pk)
        window.is_active = not window.is_active
        window.save()
        status = 'aktif' if window.is_active else 'pasif'
        messages.success(request, f'Pencere {status} yapildi.')
    except AssignmentWindow.DoesNotExist:
        messages.error(request, 'Pencere bulunamadi.')

    return redirect('core:assignment_window_list')


@login_required
def match_schedule(request):
    """Tum gorevliler icin haftalik mac programi."""
    profile = _get_profile(request)
    from collections import defaultdict
    today = date.today()

    week_offset = int(request.GET.get('week', 0))
    week_start = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    week_end = week_start + timedelta(days=6)

    league_filter = request.GET.get('league', '')

    qs = Match.objects.filter(
        date__range=(week_start, week_end)
    ).select_related('league', 'tournament', 'venue', 'assignment',
                     'assignment__head_referee__user',
                     'assignment__assistant_referee__user').order_by('date', 'time')

    if league_filter:
        qs = qs.filter(league_id=league_filter)

    # Kendi atama mac idleri
    my_match_ids = set()
    if _is_official(profile):
        my_q = _get_my_q_filter(profile)
        my_match_ids = set(Match.objects.filter(my_q).values_list('id', flat=True))

    days_dict = defaultdict(list)
    for m in qs:
        days_dict[m.date].append(m)

    weeks_data = []
    current = week_start
    while current <= week_end:
        weeks_data.append({
            'date': current,
            'day_name': _turkish_day(current),
            'matches': days_dict.get(current, []),
            'is_today': current == today,
            'is_weekend': current.weekday() >= 5,
        })
        current += timedelta(days=1)

    leagues = League.objects.all().order_by('name')

    context = {
        'profile': profile,
        'weeks_data': weeks_data,
        'my_match_ids': my_match_ids,
        'week_start': week_start,
        'week_end': week_end,
        'week_offset': week_offset,
        'prev_week': week_offset - 1,
        'next_week': week_offset + 1,
        'leagues': leagues,
        'league_filter': league_filter,
        'total_week': qs.count(),
    }
    return render(request, 'core/match_schedule.html', context)


# ─── Turnuva Yonetimi ─────────────────────────────────────────────────────────

@login_required
def tournament_list(request):
    profile = _get_profile(request)
    if not _is_admin(profile):
        return redirect('core:dashboard')
    tournaments = Tournament.objects.select_related('venue', 'created_by').order_by('-start_date')
    context = {'profile': profile, 'tournaments': tournaments}
    return render(request, 'core/tournament_list.html', context)


@login_required
def tournament_create(request):
    profile = _get_profile(request)
    if not _is_admin(profile):
        return redirect('core:dashboard')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        short_name = request.POST.get('short_name', '').strip()
        description = request.POST.get('description', '').strip()

        if not name:
            messages.error(request, 'Turnuva adi zorunludur.')
        else:
            t = Tournament.objects.create(
                name=name, short_name=short_name, description=description,
                is_active=True, created_by=request.user,
            )
            messages.success(request, f'Turnuva olusturuldu: {name}')
            return redirect('core:tournament_edit', pk=t.pk)

    context = {'profile': profile, 'editing': False}
    return render(request, 'core/tournament_form.html', context)


@login_required
def tournament_edit(request, pk):
    profile = _get_profile(request)
    if not _is_admin(profile):
        return redirect('core:dashboard')

    try:
        tournament = Tournament.objects.get(pk=pk)
    except Tournament.DoesNotExist:
        messages.error(request, 'Turnuva bulunamadi.')
        return redirect('core:tournament_list')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        short_name = request.POST.get('short_name', '').strip()
        description = request.POST.get('description', '').strip()
        is_active = request.POST.get('is_active') == 'on'

        if not name:
            messages.error(request, 'Turnuva adi zorunludur.')
        else:
            tournament.name = name
            tournament.short_name = short_name
            tournament.description = description
            tournament.is_active = is_active
            tournament.save()
            messages.success(request, f'Turnuva guncellendi: {name}')

    # GET veya POST sonrasi hep ayni sayfada kal (mac yonetimi icin)
    matches = tournament.matches.select_related('venue').order_by('date', 'time')
    from .models import Venue as VenueModel
    context = {
        'profile': profile,
        'tournament': tournament,
        'matches': matches,
        'venues': VenueModel.objects.all().order_by('name'),
        'editing': True,
    }
    return render(request, 'core/tournament_form.html', context)


@login_required
@require_POST
def tournament_match_add(request, pk):
    """Turnuvaya mac ekle (JSON POST)."""
    profile = _get_profile(request)
    if not _is_admin(profile):
        return JsonResponse({'error': 'Yetkiniz yok'}, status=403)

    try:
        tournament = Tournament.objects.get(pk=pk)
    except Tournament.DoesNotExist:
        return JsonResponse({'error': 'Turnuva bulunamadi'}, status=404)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Gecersiz veri'}, status=400)

    home_team_name = data.get('home_team_name', '').strip()
    away_team_name = data.get('away_team_name', '').strip()
    match_date_str = data.get('date', '')
    match_time_str = data.get('time', '12:00')
    venue_id = data.get('venue_id') or None
    round_info = data.get('round_info', '').strip()
    match_code = data.get('match_code', '').strip()

    if not home_team_name or not away_team_name or not match_date_str:
        return JsonResponse({'error': 'Ev sahibi, deplasman ve tarih zorunludur'}, status=400)

    try:
        from datetime import date as date_cls, datetime as dt_cls
        match_date = date_cls.fromisoformat(match_date_str)
        match_time = dt_cls.strptime(match_time_str, '%H:%M').time()
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Gecersiz tarih/saat'}, status=400)

    match = Match.objects.create(
        tournament=tournament,
        league=None,
        home_team_name=home_team_name,
        away_team_name=away_team_name,
        date=match_date,
        time=match_time,
        venue_id=venue_id,
        round_info=round_info,
        match_code=match_code,
    )

    return JsonResponse({
        'success': True,
        'match_id': match.id,
        'match_code': match.match_code,
        'home': match.home_team_name,
        'away': match.away_team_name,
        'date': match.date.strftime('%d.%m.%Y'),
        'time': match.time.strftime('%H:%M'),
        'venue': match.venue.name if match.venue else '',
        'round_info': match.round_info,
    })


@login_required
@require_POST
def tournament_match_edit(request, match_pk):
    """Turnuva macini duzenle (JSON POST)."""
    profile = _get_profile(request)
    if not _is_admin(profile):
        return JsonResponse({'error': 'Yetkiniz yok'}, status=403)

    try:
        match = Match.objects.select_related('venue').get(pk=match_pk)
    except Match.DoesNotExist:
        return JsonResponse({'error': 'Mac bulunamadi'}, status=404)

    if not match.is_tournament_match:
        return JsonResponse({'error': 'Bu mac bir turnuva maci degil'}, status=400)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Gecersiz veri'}, status=400)

    home = data.get('home_team_name', '').strip()
    away = data.get('away_team_name', '').strip()
    date_str = data.get('date', '')
    time_str = data.get('time', '')
    venue_id = data.get('venue_id') or None
    round_info = data.get('round_info', '').strip()
    match_code = data.get('match_code', '').strip()

    if not home or not away or not date_str:
        return JsonResponse({'error': 'Ev sahibi, deplasman ve tarih zorunludur'}, status=400)

    try:
        from datetime import date as date_cls, datetime as dt_cls
        match.date = date_cls.fromisoformat(date_str)
        if time_str:
            match.time = dt_cls.strptime(time_str, '%H:%M').time()
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Gecersiz tarih/saat'}, status=400)

    match.home_team_name = home
    match.away_team_name = away
    match.venue_id = venue_id
    match.round_info = round_info
    match.match_code = match_code
    match.save()

    return JsonResponse({
        'success': True,
        'match_id': match.id,
        'match_code': match.match_code,
        'home': match.home_team_name,
        'away': match.away_team_name,
        'date': match.date.strftime('%d.%m.%Y'),
        'date_iso': match.date.isoformat(),
        'time': match.time.strftime('%H:%M'),
        'venue': match.venue.name if match.venue else '',
        'venue_id': match.venue_id or '',
        'round_info': match.round_info,
    })


@login_required
@require_POST
def tournament_match_delete(request, match_pk):
    """Turnuva macini sil."""
    profile = _get_profile(request)
    if not _is_admin(profile):
        return JsonResponse({'error': 'Yetkiniz yok'}, status=403)

    try:
        match = Match.objects.get(pk=match_pk)
    except Match.DoesNotExist:
        return JsonResponse({'error': 'Mac bulunamadi'}, status=404)

    if not match.is_tournament_match:
        return JsonResponse({'error': 'Bu mac bir turnuva maci degil'}, status=400)

    match_id = match.id
    match.delete()
    return JsonResponse({'success': True, 'deleted_match_id': match_id})
