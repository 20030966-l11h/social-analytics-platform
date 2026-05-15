from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import HttpResponse
from .models import UserProfile, SocialMediaPlatform, SocialMediaPost, SentimentAnalysis, TrendPrediction
import pandas as pd
from datetime import datetime
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from sklearn.linear_model import LinearRegression
import numpy as np
import csv
from django.db.models import Sum, Count, Avg
from collections import Counter
import re


# show the login page
def login_page(request):
    # if user is already logged in, go to dashboard
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        # try to log in with the given username and password
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, 'Wrong username or password. Please try again.')
            return render(request, 'index.html', {'error': 'Wrong username or password.'})

    return render(request, 'index.html')


# handle signup form
def signup_page(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name  = request.POST.get('last_name')
        email      = request.POST.get('email')
        username   = request.POST.get('username')
        password   = request.POST.get('password')

        # check if username already taken
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already taken. Please choose another.')
            return render(request, 'index.html', {'signup_error': 'Username already taken.', 'show_signup': True})

        # check if email already used
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered.')
            return render(request, 'index.html', {'signup_error': 'Email already used.', 'show_signup': True})

        # make the new user
        new_user = User.objects.create_user(
            username=username,
            password=password,
            email=email,
            first_name=first_name,
            last_name=last_name
        )

        # give the user an analyst role by default
        UserProfile.objects.create(user=new_user, role='Analyst')

        # log them in right away
        login(request, new_user)
        return redirect('dashboard')

    return render(request, 'index.html', {'show_signup': True})


# log out and go back to login page
def logout_view(request):
    logout(request)
    return redirect('login')


# show the dashboard page
def dashboard(request):
    # if not logged in, go back to login
    if not request.user.is_authenticated:
        return redirect('login')

    # get user role to show in dashboard
    try:
        user_profile = UserProfile.objects.get(user=request.user)
        role = user_profile.role
    except UserProfile.DoesNotExist:
        role = 'Analyst'

    # total posts in db
    total_posts = SocialMediaPost.objects.count()

    # sentiment stats
    total_analysed = SentimentAnalysis.objects.count()
    positive_count = SentimentAnalysis.objects.filter(sentiment_label='positive').count()
    negative_count = SentimentAnalysis.objects.filter(sentiment_label='negative').count()

    # work out percentages
    pos_pct = 0
    neg_pct = 0
    neu_pct = 0
    if total_analysed > 0:
        pos_pct = round((positive_count / total_analysed) * 100)
        neg_pct = round((negative_count / total_analysed) * 100)
        neu_pct = 100 - pos_pct - neg_pct

    # count total trending hashtags predicted
    trending_count = TrendPrediction.objects.filter(predicted_trend='rising').count()

    # count how many platforms we have
    platform_count = SocialMediaPlatform.objects.count()

    # get top 3 rising hashtags by confidence to show in word cloud
    top_hashtags = TrendPrediction.objects.filter(predicted_trend='rising').order_by('-confidence_score')[:3]

    context = {
        'user': request.user,
        'role': role,
        'total_posts': total_posts,
        'pos_pct': pos_pct,
        'neg_pct': neg_pct,
        'neu_pct': neu_pct,
        'trending_count': trending_count,
        'platform_count': platform_count,
        'top_hashtags': top_hashtags,
    }
    return render(request, 'dashboard.html', context)


# show upload page and handle csv file upload
def upload_page(request):
    if not request.user.is_authenticated:
        return redirect('login')

    if request.method == 'POST':
        # check if a file was sent
        csv_file = request.FILES.get('csv_file')

        if not csv_file:
            return render(request, 'upload.html', {'upload_error': 'Please choose a file to upload.'})

        # check if file is csv
        if not csv_file.name.endswith('.csv'):
            return render(request, 'upload.html', {'upload_error': 'Only CSV files are allowed.'})

        # read the csv file with pandas
        try:
            df = pd.read_csv(csv_file)
        except Exception as e:
            return render(request, 'upload.html', {'upload_error': 'Could not read the file. Make sure it is a valid CSV.'})

        # count rows before cleaning
        rows_before = len(df)

        # drop rows that are exactly the same
        df = df.drop_duplicates()

        # check if required columns exist
        required_columns = ['Text', 'Platform', 'User']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            return render(request, 'upload.html', {
                'upload_error': f'Missing required columns: {", ".join(missing_columns)}. Please check your CSV format.'
            })

        # drop rows where important columns are missing
        df = df.dropna(subset=required_columns)

        # count rows after cleaning
        rows_after = len(df)
        rows_dropped = rows_before - rows_after

        saved_count = 0
        error_count = 0

        # go through each row and save to db
        for index, row in df.iterrows():
            try:
                # get or create the platform
                platform_name = str(row['Platform']).strip()
                platform, created = SocialMediaPlatform.objects.get_or_create(name=platform_name)

                # calculate engagement (likes + retweets)
                likes = 0
                retweets = 0
                if 'Likes' in df.columns and not pd.isna(row['Likes']):
                    likes = int(row['Likes'])
                if 'Retweets' in df.columns and not pd.isna(row['Retweets']):
                    retweets = int(row['Retweets'])
                engagement = likes + retweets

                # get hashtags if they exist
                hashtags = ''
                if 'Hashtags' in df.columns and not pd.isna(row['Hashtags']):
                    hashtags = str(row['Hashtags'])

                # build the post date from year, month, day, hour columns
                post_date = datetime.now()
                if 'Year' in df.columns and 'Month' in df.columns and 'Day' in df.columns:
                    try:
                        year  = int(row['Year'])
                        month = int(row['Month'])
                        day   = int(row['Day'])
                        hour  = 0
                        if 'Hour' in df.columns and not pd.isna(row['Hour']):
                            hour = int(row['Hour'])
                        post_date = datetime(year, month, day, hour)
                    except:
                        # if date is bad just use now
                        post_date = datetime.now()

                # save the post to db
                SocialMediaPost.objects.create(
                    platform=platform,
                    content_text=str(row['Text']),
                    author=str(row['User']),
                    post_date=post_date,
                    engagement_count=engagement,
                    hashtags=hashtags
                )
                saved_count += 1

            except Exception as e:
                # skip this row if something goes wrong
                error_count += 1
                continue

        context = {
            'upload_success': True,
            'rows_before': rows_before,
            'rows_after': rows_after,
            'rows_dropped': rows_dropped,
            'saved_count': saved_count,
            'error_count': error_count,
        }
        return render(request, 'upload.html', context)

    return render(request, 'upload.html')


# run vader on one post and return the label and score
def analyse_one_post(text):
    analyser = SentimentIntensityAnalyzer()
    scores = analyser.polarity_scores(text)
    score = scores['compound']

    # decide label based on score
    if score > 0.05:
        label = 'positive'
    elif score < -0.05:
        label = 'negative'
    else:
        label = 'neutral'

    return label, score


# show sentiment page and run analysis
def sentiment_page(request):
    if not request.user.is_authenticated:
        return redirect('login')

    # if user clicked run analysis button
    if request.method == 'POST':
        # get all posts that do not have a sentiment yet
        posts_without_sentiment = SocialMediaPost.objects.filter(sentimentanalysis__isnull=True)
        new_count = 0

        for post in posts_without_sentiment:
            label, score = analyse_one_post(post.content_text)

            # save the result to db
            SentimentAnalysis.objects.create(
                post=post,
                sentiment_label=label,
                sentiment_score=score
            )
            new_count += 1

    # count how many of each label we have
    total_analysed = SentimentAnalysis.objects.count()
    positive_count = SentimentAnalysis.objects.filter(sentiment_label='positive').count()
    negative_count = SentimentAnalysis.objects.filter(sentiment_label='negative').count()
    neutral_count  = SentimentAnalysis.objects.filter(sentiment_label='neutral').count()

    # work out percentages for the progress bars
    pos_pct = 0
    neu_pct = 0
    neg_pct = 0
    if total_analysed > 0:
        pos_pct = round((positive_count / total_analysed) * 100)
        neu_pct = round((neutral_count  / total_analysed) * 100)
        neg_pct = round((negative_count / total_analysed) * 100)

    # get the last 12 posts with their sentiment to show in the table
    recent_results = SentimentAnalysis.objects.select_related('post', 'post__platform').order_by('-id')[:12]

    # count posts that still need analysis
    unanalysed_count = SocialMediaPost.objects.filter(sentimentanalysis__isnull=True).count()

    context = {
        'total_analysed': total_analysed,
        'positive_count': positive_count,
        'negative_count': negative_count,
        'neutral_count':  neutral_count,
        'pos_pct': pos_pct,
        'neu_pct': neu_pct,
        'neg_pct': neg_pct,
        'recent_results': recent_results,
        'unanalysed_count': unanalysed_count,
    }
    return render(request, 'sentiment.html', context)


# use linear regression to predict if a hashtag is rising, stable, or falling
def predict_one_hashtag(hashtag):
    # get all posts that have this hashtag
    posts = SocialMediaPost.objects.filter(hashtags__icontains=hashtag).order_by('post_date')

    if posts.count() < 2:
        # not enough data to do regression
        return 'stable', 0.5

    # group posts by day and add up engagement
    day_engagement = {}
    for post in posts:
        day_key = post.post_date.date()
        if day_key not in day_engagement:
            day_engagement[day_key] = 0
        day_engagement[day_key] += post.engagement_count

    # sort by day
    sorted_days = sorted(day_engagement.keys())

    if len(sorted_days) < 2:
        return 'stable', 0.5

    # make x values (day number 0, 1, 2 ...) and y values (engagement)
    x_vals = []
    y_vals = []
    for i, day in enumerate(sorted_days):
        x_vals.append(i)
        y_vals.append(day_engagement[day])

    # reshape for sklearn
    x = np.array(x_vals).reshape(-1, 1)
    y = np.array(y_vals)

    # fit the model
    model = LinearRegression()
    model.fit(x, y)

    # the slope tells us if engagement is going up or down
    slope = model.coef_[0]

    # r squared tells us how confident we are (0 to 1)
    r_squared = model.score(x, y)
    confidence = round(abs(r_squared), 2)

    # decide the trend label based on slope
    avg_engagement = np.mean(y_vals)
    if avg_engagement == 0:
        avg_engagement = 1

    # compare slope to average to get relative change
    relative_slope = slope / avg_engagement

    if relative_slope > 0.05:
        trend = 'rising'
    elif relative_slope < -0.05:
        trend = 'falling'
    else:
        trend = 'stable'

    return trend, confidence


# show trends page and run predictions
def trends_page(request):
    if not request.user.is_authenticated:
        return redirect('login')

    if request.method == 'POST':
        # delete old predictions first so we get fresh ones
        TrendPrediction.objects.all().delete()

        # get all unique hashtags from the posts
        all_posts = SocialMediaPost.objects.exclude(hashtags='').exclude(hashtags__isnull=True)

        # collect all hashtag strings into one list
        hashtag_set = set()
        for post in all_posts:
            # hashtags can be comma separated or space separated
            tags = post.hashtags.replace(',', ' ').split()
            for tag in tags:
                tag = tag.strip()
                if tag:
                    hashtag_set.add(tag)

        # run prediction for each hashtag
        for hashtag in hashtag_set:
            trend_label, confidence = predict_one_hashtag(hashtag)

            # save to db
            TrendPrediction.objects.create(
                hashtag=hashtag,
                predicted_trend=trend_label,
                confidence_score=confidence
            )

    # get all predictions to show
    all_predictions = TrendPrediction.objects.all().order_by('-confidence_score')

    rising_count  = TrendPrediction.objects.filter(predicted_trend='rising').count()
    falling_count = TrendPrediction.objects.filter(predicted_trend='falling').count()
    stable_count  = TrendPrediction.objects.filter(predicted_trend='stable').count()
    total_count   = TrendPrediction.objects.count()

    context = {
        'all_predictions': all_predictions,
        'rising_count': rising_count,
        'falling_count': falling_count,
        'stable_count': stable_count,
        'total_count': total_count,
    }
    return render(request, 'trends.html', context)


# show reports page
def reports_page(request):
    if not request.user.is_authenticated:
        return redirect('login')

    # count records to show on the page
    total_posts     = SocialMediaPost.objects.count()
    total_sentiment = SentimentAnalysis.objects.count()
    total_trends    = TrendPrediction.objects.count()

    context = {
        'total_posts': total_posts,
        'total_sentiment': total_sentiment,
        'total_trends': total_trends,
    }
    return render(request, 'reports.html', context)


# download all sentiment results as a csv file
def download_csv(request):
    if not request.user.is_authenticated:
        return redirect('login')

    # tell the browser to download a file called report.csv
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="sentiment_report.csv"'

    # write the csv rows
    writer = csv.writer(response)

    # header row
    writer.writerow(['Post ID', 'Platform', 'Author', 'Post Date', 'Engagement', 'Hashtags', 'Content', 'Sentiment Label', 'Sentiment Score'])

    # get all sentiment results with related post and platform
    results = SentimentAnalysis.objects.select_related('post', 'post__platform').all()

    for result in results:
        post = result.post
        writer.writerow([
            post.id,
            post.platform.name,
            post.author,
            post.post_date.strftime('%Y-%m-%d %H:%M'),
            post.engagement_count,
            post.hashtags,
            post.content_text[:200],
            result.sentiment_label,
            round(result.sentiment_score, 4),
        ])

    return response


# show topics page
def topics_page(request):
    if not request.user.is_authenticated:
        return redirect('login')

    all_posts = SocialMediaPost.objects.all()
    
    # Extract Hashtags
    hashtag_list = []
    for post in all_posts:
        if post.hashtags:
            # support both space and comma separation
            tags = re.split(r'[,\s]+', post.hashtags)
            hashtag_list.extend([t.strip().lower() for t in tags if t.strip()])
    
    hashtag_counts = Counter(hashtag_list).most_common(10)
    top_hashtags = [{'name': h[0], 'count': h[1]} for h in hashtag_counts]
    
    # Extract Keywords (simple)
    word_list = []
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'with', 'is', 'are', 'was', 'were'}
    for post in all_posts:
        words = re.findall(r'\w+', post.content_text.lower())
        word_list.extend([w for w in words if len(w) > 3 and w not in stop_words])
    
    keyword_counts = Counter(word_list).most_common(10)
    top_keywords = [{'name': k[0], 'count': k[1]} for k in keyword_counts]

    context = {
        'total_topics': len(set(hashtag_list)),
        'top_hashtags': top_hashtags,
        'top_keywords': top_keywords,
        'hashtag_list_raw': hashtag_counts[:20], # for word cloud
    }
    return render(request, 'topics.html', context)


# show audience page
def audience_page(request):
    if not request.user.is_authenticated:
        return redirect('login')

    # Top Influencers by engagement
    influencers = SocialMediaPost.objects.values('author', 'platform__name') \
        .annotate(total_posts=Count('id'), total_engagement=Sum('engagement_count')) \
        .order_by('-total_engagement')[:10]

    # Peak Activity Hours
    hour_activity = SocialMediaPost.objects.values('hour') \
        .annotate(post_count=Count('id')) \
        .order_by('hour')
    
    # Engagement Over Time (last 7 unique days in data)
    engagement_time = SocialMediaPost.objects.values('post_date__date') \
        .annotate(likes=Sum('engagement_count')) \
        .order_by('-post_date__date')[:7]

    context = {
        'total_audience': SocialMediaPost.objects.values('author').distinct().count(),
        'influencers': influencers,
        'hour_activity': list(hour_activity),
        'engagement_time': list(reversed(engagement_time)),
    }
    return render(request, 'audience.html', context)


# show platforms page
def platforms_page(request):
    if not request.user.is_authenticated:
        return redirect('login')

    platforms_data = SocialMediaPlatform.objects.annotate(
        post_count=Count('socialmediapost'),
        avg_engagement=Avg('socialmediapost__engagement_count'),
    )

    # Calculate sentiment per platform
    platform_sentiment = []
    for p in platforms_data:
        sentiment_stats = SentimentAnalysis.objects.filter(post__platform=p) \
            .values('sentiment_label') \
            .annotate(count=Count('id'))
        
        total = sum(s['count'] for s in sentiment_stats)
        pos = next((s['count'] for s in sentiment_stats if s['sentiment_label'] == 'positive'), 0)
        pos_pct = round((pos / total * 100)) if total > 0 else 0
        
        platform_sentiment.append({
            'platform': p,
            'pos_pct': pos_pct,
            'total': total,
        })

    context = {
        'platform_count': platforms_data.count(),
        'total_posts': SocialMediaPost.objects.count(),
        'platform_sentiment': platform_sentiment,
    }
    return render(request, 'platforms.html', context)
