from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('hakem', 'Hakem'),
        ('masa_gorevlisi', 'Masa Gorevlisi'),
        ('gozlemci', 'Gozlemci'),
        ('atama_sorumlusu', 'Atama Sorumlusu'),
        ('il_temsilcisi', 'Il Temsilcisi'),
    ]

    CLASSIFICATION_CHOICES = [
        ('A', 'A Klasman'),
        ('B', 'B Klasman'),
        ('C', 'C Klasman'),
        ('il', 'Il Hakemi'),
        ('aday', 'Aday Hakem'),
        ('', 'Belirsiz'),
    ]

    # Klasman sirasi (kucuk = oncelikli)
    CLASSIFICATION_ORDER = {'A': 0, 'B': 1, 'C': 2, 'il': 3, 'aday': 4, '': 5}

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    phone = models.CharField(max_length=20, blank=True)
    is_active_official = models.BooleanField(default=True)
    classification = models.CharField(
        max_length=10, blank=True, choices=CLASSIFICATION_CHOICES,
        verbose_name='Klasman', help_text='Sadece hakemler icin gecerlidir'
    )

    class Meta:
        verbose_name = 'Kullanici Profili'
        verbose_name_plural = 'Kullanici Profilleri'

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.get_role_display()})"

    @property
    def full_name(self):
        return self.user.get_full_name() or self.user.username

    @property
    def display_name(self):
        """Klasman rozeti ile birlikte isim."""
        name = self.full_name
        if self.role == 'hakem' and self.classification:
            return f"{name} ({self.classification})"
        return name

    @property
    def classification_order(self):
        return self.CLASSIFICATION_ORDER.get(self.classification, 5)


class League(models.Model):
    CATEGORY_CHOICES = [
        ('a_ligi', 'A Ligi'),
        ('b_ligi', 'B Ligi'),
        ('gencler', 'Gencler'),
        ('kucukler', 'Kucukler'),
        ('diger', 'Diger'),
    ]

    tbf_id = models.IntegerField(unique=True, help_text='TBF faaliyetId')
    name = models.CharField(max_length=200)
    age_group = models.CharField(max_length=50)
    gender = models.CharField(max_length=20)
    season = models.CharField(max_length=20, default='2025-2026')
    season_id = models.IntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, default='diger',
        verbose_name='Kategori',
        help_text='A Ligi, B Ligi gibi kategoriler icin kullanilir',
    )

    class Meta:
        verbose_name = 'Lig'
        verbose_name_plural = 'Ligler'
        ordering = ['name']

    def __str__(self):
        return self.name


class Tournament(models.Model):
    """Ozel turnuvalar - TBF API'den senkronize edilmez, manuel olusturulur."""
    name = models.CharField(max_length=200, verbose_name='Turnuva Adi')
    short_name = models.CharField(max_length=50, blank=True, verbose_name='Kisa Ad')
    description = models.TextField(blank=True, verbose_name='Aciklama')
    start_date = models.DateField(null=True, blank=True, verbose_name='Baslangic Tarihi')
    end_date = models.DateField(null=True, blank=True, verbose_name='Bitis Tarihi')
    venue = models.ForeignKey(
        'Venue', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='Salon',
    )
    is_active = models.BooleanField(default=True, verbose_name='Aktif')
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='Olusturan',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Turnuva'
        verbose_name_plural = 'Turnuvalar'
        ordering = ['-start_date']

    def __str__(self):
        return self.name

    @property
    def match_count(self):
        return self.matches.count()


class Team(models.Model):
    tbf_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=200)
    league = models.ForeignKey(League, on_delete=models.CASCADE, related_name='teams')
    logo_url = models.URLField(blank=True)

    class Meta:
        verbose_name = 'Takim'
        verbose_name_plural = 'Takimlar'
        ordering = ['name']

    def __str__(self):
        return self.name


class Venue(models.Model):
    name = models.CharField(max_length=200, unique=True)

    class Meta:
        verbose_name = 'Salon'
        verbose_name_plural = 'Salonlar'
        ordering = ['name']

    def __str__(self):
        return self.name


class Match(models.Model):
    tbf_match_id = models.IntegerField(unique=True, null=True, blank=True)
    match_code = models.CharField(max_length=20, blank=True)
    league = models.ForeignKey(
        League, on_delete=models.SET_NULL, null=True, blank=True, related_name='matches',
    )
    tournament = models.ForeignKey(
        'Tournament', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='matches', verbose_name='Turnuva',
    )
    home_team_name = models.CharField(max_length=200)
    away_team_name = models.CharField(max_length=200)
    home_team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='home_matches')
    away_team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='away_matches')
    venue = models.ForeignKey(Venue, on_delete=models.SET_NULL, null=True, blank=True)
    date = models.DateField()
    time = models.TimeField()
    week = models.CharField(max_length=50, blank=True)
    round_info = models.CharField(max_length=100, blank=True, help_text='Yari Final, Final vb.')
    home_score = models.IntegerField(null=True, blank=True)
    away_score = models.IntegerField(null=True, blank=True)
    is_played = models.BooleanField(default=False)
    match_status_id = models.IntegerField(null=True, blank=True)

    class Meta:
        verbose_name = 'Mac'
        verbose_name_plural = 'Maclar'
        ordering = ['date', 'time']

    def __str__(self):
        return f"{self.match_code} - {self.home_team_name} vs {self.away_team_name} ({self.date})"

    @property
    def is_upcoming(self):
        from django.utils import timezone
        from datetime import datetime
        match_dt = datetime.combine(self.date, self.time)
        return timezone.make_aware(match_dt) > timezone.now()

    @property
    def competition_name(self):
        if self.tournament_id:
            return self.tournament.name if self.tournament else ''
        return self.league.name if self.league_id and self.league else ''

    @property
    def is_tournament_match(self):
        return self.tournament_id is not None


class Availability(models.Model):
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='availabilities')
    date = models.DateField()
    is_available = models.BooleanField(default=True)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Musaitlik'
        verbose_name_plural = 'Musaitlikler'
        unique_together = ['user', 'date']
        ordering = ['date']

    def __str__(self):
        status = 'Musait' if self.is_available else 'Musait Degil'
        return f"{self.user.full_name} - {self.date} - {status}"


class AvailabilityRequest(models.Model):
    """Yoneticinin gorevlilerden musaitlik istemesi icin olusturulan istek."""
    title = models.CharField(max_length=200, verbose_name='Baslik')
    description = models.TextField(blank=True, verbose_name='Aciklama')
    # Eski alan - geri uyumluluk icin nullable
    start_date = models.DateField(null=True, blank=True, verbose_name='Baslangic Tarihi')
    end_date = models.DateField(null=True, blank=True, verbose_name='Bitis Tarihi')
    # Yeni: virgul ile ayrilmis ISO tarihleri "2026-04-03,2026-04-06,2026-04-07"
    specific_dates = models.TextField(
        blank=True,
        verbose_name='Secilen Gunler',
        help_text='Virgul ile ayrilmis ISO tarihler: 2026-04-03,2026-04-06'
    )
    target_roles = models.CharField(
        max_length=100, default='hakem,masa_gorevlisi,gozlemci',
        help_text='Virgul ile ayrilmis roller'
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    deadline = models.DateTimeField(null=True, blank=True, verbose_name='Son Bildirim Tarihi')

    class Meta:
        verbose_name = 'Musaitlik Istegi'
        verbose_name_plural = 'Musaitlik Istekleri'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def date_list(self):
        """Secilen gunlerin listesi. specific_dates varsa onu kullan, yoksa aralik."""
        from datetime import date as date_cls
        if self.specific_dates:
            dates = []
            for s in self.specific_dates.split(','):
                s = s.strip()
                if s:
                    try:
                        dates.append(date_cls.fromisoformat(s))
                    except ValueError:
                        pass
            return sorted(dates)
        # Geri uyumluluk: aralik varsa kullan
        if self.start_date and self.end_date:
            from datetime import timedelta
            dates = []
            d = self.start_date
            while d <= self.end_date:
                dates.append(d)
                d += timedelta(days=1)
            return dates
        return []

    # Geri uyumluluk alias
    @property
    def date_range(self):
        return self.date_list

    @property
    def target_role_list(self):
        return [r.strip() for r in self.target_roles.split(',') if r.strip()]

    @property
    def deadline_passed(self):
        if not self.deadline:
            return False
        from django.utils import timezone
        return timezone.now() > self.deadline

    def get_response_count(self):
        roles = self.target_role_list
        total = UserProfile.objects.filter(role__in=roles, is_active_official=True).count()
        dates = self.date_list
        if not dates:
            return 0, total
        responded = Availability.objects.filter(
            date__in=dates,
            user__role__in=roles,
            user__is_active_official=True
        ).values('user').distinct().count()
        return responded, total


class AssignmentWindow(models.Model):
    """Atama yapilabilecek zaman araligini belirler. Bu aralik disinda atama yapilamaz."""
    title = models.CharField(max_length=200, verbose_name='Baslik')
    start_datetime = models.DateTimeField(verbose_name='Acilis Zamani')
    end_datetime = models.DateTimeField(verbose_name='Kapanis Zamani')
    is_active = models.BooleanField(default=True, verbose_name='Aktif')
    tournament = models.ForeignKey(
        'Tournament', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assignment_windows', verbose_name='Turnuva',
        help_text='Bos=global (lig maclari). Secilirse sadece o turnuva icin gecerlidir.',
    )
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True, verbose_name='Not')

    class Meta:
        verbose_name = 'Atama Penceresi'
        verbose_name_plural = 'Atama Pencereleri'
        ordering = ['-created_at']

    def __str__(self):
        scope = f' [{self.tournament.name}]' if self.tournament_id else ' [Global]'
        return f"{self.title}{scope} ({self.start_datetime:%d.%m.%Y %H:%M} - {self.end_datetime:%d.%m.%Y %H:%M})"

    @classmethod
    def get_active(cls):
        """Simdi acik olan global pencereyi dondur (lig maclari icin)."""
        from django.utils import timezone
        now = timezone.now()
        return cls.objects.filter(
            is_active=True,
            tournament__isnull=True,
            start_datetime__lte=now,
            end_datetime__gte=now,
        ).first()

    @classmethod
    def is_open(cls):
        return cls.get_active() is not None

    @classmethod
    def is_open_for_match(cls, match):
        """
        Belirli bir mac icin atama penceresi acik mi?
        - Turnuva maci: turnuva penceresi VEYA global pencere yeterli.
        - Lig maci: sadece global pencere (tournament=NULL).
        """
        from django.utils import timezone
        now = timezone.now()
        qs = cls.objects.filter(is_active=True, start_datetime__lte=now, end_datetime__gte=now)
        if match.is_tournament_match:
            return qs.filter(
                models.Q(tournament_id=match.tournament_id) | models.Q(tournament__isnull=True)
            ).exists()
        else:
            return qs.filter(tournament__isnull=True).exists()

    @property
    def status(self):
        from django.utils import timezone
        now = timezone.now()
        if not self.is_active:
            return 'disabled'
        if now < self.start_datetime:
            return 'upcoming'
        if now > self.end_datetime:
            return 'expired'
        return 'open'


class Assignment(models.Model):
    match = models.OneToOneField(Match, on_delete=models.CASCADE, related_name='assignment')
    head_referee = models.ForeignKey(
        UserProfile, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='head_referee_assignments', verbose_name='Bas Hakem'
    )
    assistant_referee = models.ForeignKey(
        UserProfile, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assistant_referee_assignments', verbose_name='Yardimci Hakem'
    )
    scorer_1 = models.ForeignKey(
        UserProfile, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='scorer1_assignments', verbose_name='Sayi Gorevlisi 1'
    )
    scorer_2 = models.ForeignKey(
        UserProfile, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='scorer2_assignments', verbose_name='Sayi Gorevlisi 2'
    )
    timer = models.ForeignKey(
        UserProfile, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='timer_assignments', verbose_name='Sure Gorevlisi'
    )
    shot_clock = models.ForeignKey(
        UserProfile, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='shot_clock_assignments', verbose_name='Sut Saati Gorevlisi'
    )
    observer = models.ForeignKey(
        UserProfile, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='observer_assignments', verbose_name='Gozlemci'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_assignments'
    )

    class Meta:
        verbose_name = 'Atama'
        verbose_name_plural = 'Atamalar'

    def __str__(self):
        return f"Atama: {self.match}"

    def get_all_assigned_users(self):
        users = []
        for field in ['head_referee', 'assistant_referee', 'scorer_1', 'scorer_2', 'timer', 'shot_clock', 'observer']:
            user = getattr(self, field)
            if user:
                users.append(user)
        return users
