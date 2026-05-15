from django.db import models
from django.contrib.auth.models import User


# this model adds a role to the normal django user
class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('Admin', 'Admin'),
        ('Analyst', 'Analyst'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='Analyst')

    def __str__(self):
        return self.user.username + ' - ' + self.role


# this stores the social media platform name like twitter or instagram
class SocialMediaPlatform(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


# this stores each post we get from the csv file
class SocialMediaPost(models.Model):
    platform = models.ForeignKey(SocialMediaPlatform, on_delete=models.CASCADE)
    content_text = models.TextField()
    author = models.CharField(max_length=200)
    post_date = models.DateTimeField()
    # engagement is likes + retweets added together
    engagement_count = models.IntegerField(default=0)
    hashtags = models.CharField(max_length=500, blank=True)

    def __str__(self):
        return self.author + ' - ' + self.content_text[:50]


# this stores the sentiment result for each post
class SentimentAnalysis(models.Model):
    SENTIMENT_CHOICES = [
        ('positive', 'positive'),
        ('neutral', 'neutral'),
        ('negative', 'negative'),
    ]
    post = models.ForeignKey(SocialMediaPost, on_delete=models.CASCADE)
    sentiment_label = models.CharField(max_length=20, choices=SENTIMENT_CHOICES)
    # score is a number between -1 and 1
    sentiment_score = models.FloatField()

    def __str__(self):
        return self.sentiment_label + ' (' + str(self.sentiment_score) + ')'


# this stores the prediction for a hashtag if it is going up or down
class TrendPrediction(models.Model):
    TREND_CHOICES = [
        ('rising', 'rising'),
        ('stable', 'stable'),
        ('falling', 'falling'),
    ]
    hashtag = models.CharField(max_length=200)
    predicted_trend = models.CharField(max_length=20, choices=TREND_CHOICES)
    # confidence is how sure the model is, between 0 and 1
    confidence_score = models.FloatField()
    prediction_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.hashtag + ' - ' + self.predicted_trend


# this stores the report a user downloads
class Report(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    file_type = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.username + ' report - ' + self.file_type
