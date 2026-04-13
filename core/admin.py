from django.contrib import admin
from .models import UserProfile, League, Team, Venue, Match, Availability, AvailabilityRequest, Assignment


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'phone', 'is_active_official']
    list_filter = ['role', 'is_active_official']
    search_fields = ['user__first_name', 'user__last_name', 'user__username']


@admin.register(League)
class LeagueAdmin(admin.ModelAdmin):
    list_display = ['name', 'age_group', 'gender', 'season', 'tbf_id', 'is_active']
    list_filter = ['age_group', 'gender', 'season']


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ['name', 'league', 'tbf_id']
    list_filter = ['league']
    search_fields = ['name']


@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ['match_code', 'league', 'home_team_name', 'away_team_name', 'date', 'time', 'venue', 'is_played']
    list_filter = ['league', 'date', 'is_played']
    search_fields = ['match_code', 'home_team_name', 'away_team_name']
    date_hierarchy = 'date'


@admin.register(Availability)
class AvailabilityAdmin(admin.ModelAdmin):
    list_display = ['user', 'date', 'is_available', 'note']
    list_filter = ['is_available', 'date', 'user__role']
    date_hierarchy = 'date'


@admin.register(AvailabilityRequest)
class AvailabilityRequestAdmin(admin.ModelAdmin):
    list_display = ['title', 'start_date', 'end_date', 'is_active', 'created_at']
    list_filter = ['is_active']


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ['match', 'head_referee', 'assistant_referee', 'observer']
    list_filter = ['match__date', 'match__league']
    raw_id_fields = ['match', 'head_referee', 'assistant_referee', 'scorer_1', 'scorer_2', 'timer', 'shot_clock', 'observer']
