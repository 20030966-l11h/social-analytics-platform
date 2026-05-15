from django.contrib import admin
from .models import UserProfile, SocialMediaPlatform, SocialMediaPost, SentimentAnalysis, TrendPrediction, Report

# register all models so we can see them in the admin panel

admin.site.register(UserProfile)
admin.site.register(SocialMediaPlatform)
admin.site.register(SocialMediaPost)
admin.site.register(SentimentAnalysis)
admin.site.register(TrendPrediction)
admin.site.register(Report)
