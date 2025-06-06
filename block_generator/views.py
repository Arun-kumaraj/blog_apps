from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
from pytube import YouTube
import os
import yt_dlp
import google.generativeai as genai
import assemblyai as aai
from django.conf import settings
from .models import BlogPost
from dotenv import load_dotenv

load_dotenv()

# ✅ Configure Google Gemini API
genai.configure(api_key=os.getenv('API_key_gai'))

@login_required
def index(request):
    return render(request, 'index.html')

@csrf_exempt
def generate_blog(request):
    if request.method == 'POST':
        try:
            # ✅ Get YouTube link from POST data
            data = json.loads(request.body)
            yt_link = data['link']
        except (KeyError, json.JSONDecodeError):
            return JsonResponse({'error': 'Invalid data sent'}, status=400)

        # ✅ Extract video title
        title = yt_title(yt_link)
        # ✅ Transcribe the audio
        transcription = get_transcription(yt_link)

        # ✅ Check if transcription was successful
        if not transcription:
            return JsonResponse({'error': "Failed to get transcript"}, status=500)

        # ✅ Generate blog content from transcription
        blog_content = generate_blog_from_transcription(transcription)

        if not blog_content:
            return JsonResponse({'error': "Failed to generate blog article"}, status=500)

        # ✅ Save content to database
        new_blog_article = BlogPost.objects.create(
            user=request.user,
            youtube_title=title,
            youtube_link=yt_link,
            generated_content=blog_content,
        )
        new_blog_article.save()

        # ✅ Convert content to bullet points
        bullet_points = "\n".join([f"* {line.strip()}" for line in blog_content.split("\n") if line.strip()])

        return JsonResponse({'content': bullet_points})
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)

def yt_title(link):
    # ✅ Extract video title from YouTube URL
    ydl_opts = {'quiet': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(link, download=False)
        return info.get('title', 'YouTube Video')

def download_audio(link):
    # ✅ Set media path
    media_path = os.path.join(settings.MEDIA_ROOT, 'audio')
    if not os.path.exists(media_path):
        os.makedirs(media_path)

    # ✅ Download audio as MP3
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(media_path, '%(title)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    # ✅ Extract audio from YouTube
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(link, download=True)
        filename = ydl.prepare_filename(info_dict)
        audio_file = filename.rsplit('.', 1)[0] + '.mp3'

    return audio_file

def get_transcription(link):
    # ✅ Download audio file
    audio_file = download_audio(link)

    # ✅ AssemblyAI API Key
    aai.settings.api_key = os.getenv('API_key_ai')

    # ✅ Transcribe audio file
    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(audio_file)

    return transcript.text

def generate_blog_from_transcription(transcription):
    try:
        # ✅ Correct the Gemini Model name (fixed the 404 error)
        model = genai.GenerativeModel('gemini-1.5-pro')

        # ✅ Generate content from transcription
        response = model.generate_content(transcription)

        # ✅ Handle empty response
        if not response.candidates:
            return "No content generated by Gemini API."

        # ✅ Extract the generated text
        return response.text if hasattr(response, "text") else "Content generation failed."

    except Exception as e:
        # ✅ Handle API error
        print(f"Error from Gemini API: {e}")
        return "Failed to generate blog due to content restrictions."

def blog_list(request):
    blog_articles = BlogPost.objects.filter(user=request.user)
    return render(request, 'All-blog.html', {'blog_articles': blog_articles})

def blog_details(request, pk):
    # ✅ Fetch blog post
    blog_article_detail = BlogPost.objects.get(id=pk)

    # ✅ Ensure only the owner can see the blog
    if request.user == blog_article_detail.user:
        content_list = [line.strip() for line in blog_article_detail.generated_content.split('.')]
        return render(request, 'blog-details.html', {'blog_article_detail': blog_article_detail, 'content_list': content_list})
    else:
        return redirect('/')

# ✅ Authentication Methods
def user_login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('/')
        else:
            return render(request, 'login.html', {'error_message': "Invalid username or password"})
    return render(request, 'login.html')

def user_signup(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        repeatPassword = request.POST['repeatPassword']
        if password == repeatPassword:
            try:
                user = User.objects.create_user(username, email, password)
                login(request, user)
                return redirect('/')
            except:
                return render(request, 'signup.html', {'error_message': 'Error creating account'})
        else:
            return render(request, 'signup.html', {'error_message': 'Passwords do not match'})
    return render(request, 'signup.html')

def user_logout(request):
    logout(request)
    return redirect('/')
