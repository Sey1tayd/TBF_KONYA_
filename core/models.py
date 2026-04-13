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

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    phone = models.CharField(max_length=20, blank=True)
    is_active_official = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Kullanici Profili'
        verbose_name_plural = 'Kullanici Profilleri'

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.get_role_display()})"

    @property
    def full_name(self):
        return self.user.get_full_name() or self.user.username


class League(models.Model):
    tbf_id = models.IntegerField(unique=True, help_text='TBF faaliyetId')
    name = models.CharField(max_length=200)
    age_group = models.CharField(max_length=50)
    gender = models.CharField(max_length=20)
    season = models.CharField(max_length=20, default='2025-2026')
    season_id = models.IntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Lig'
        verbose_name_plural = 'Ligler'
        ordering = ['name']

    def __str__(self):
        return self.name


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
    league = models.ForeignKey(League, on_delete=models.CASCADE, related_name='matches')
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
    start_date = models.DateField(verbose_name='Baslangic Tarihi')
    end_date = models.DateField(verbose_name='Bitis Tarihi')
    target_roles = models.CharField(
        max_length=100, default='hakem,masa_gorevlisi,gozlemci',
        help_text='Virgul ile ayrilmis roller: hakem,masa_gorevlisi,gozlemci'
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
        return f"{self.title} ({self.start_date} - {self.end_date})"

    @property
    def date_range(self):
        from datetime import timedelta
        dates = []
        d = self.start_date
        while d <= self.end_date:
            dates.append(d)
            d += timedelta(days=1)
        return dates

    @property
    def target_role_list(self):
        return [r.strip() for r in self.target_roles.split(',') if r.strip()]

    def get_response_count(self):
        roles = self.target_role_list
        total = UserProfile.objects.filter(role__in=roles, is_active_official=True).count()
        responded = Availability.objects.filter(
            date__range=(self.start_date, self.end_date),
            user__role__in=roles,
            user__is_active_official=True
        ).values('user').distinct().count()
        return responded, total


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
