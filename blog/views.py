from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Count
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from taggit.models import Tag
from .forms import EmailPostForm, CommentForm, PostForm
from .models import Post
from django.views.generic import ListView
from django.core.mail import send_mail
from django.contrib.auth.decorators import login_required

from ibm_watson.tone_analyzer_v3 import ToneInput
import requests
import json
from ibm_watson import ToneAnalyzerV3
from ibm_watson.tone_analyzer_v3 import ToneInput
from ibm_watson import LanguageTranslatorV3

language_translator = LanguageTranslatorV3(
    version='2018-05-01',
    iam_apikey='pnfzBR-yllY5eRIvXHjV1aM3ClvHlCAIe_7GdAmZwdFF')

tone_analyzer = ToneAnalyzerV3(
    version='2017-09-21',
    iam_apikey='zUq8VmS5pGghqI8TaNIMIm-D-q_gCvCzJ9G2-z2LQh9C',
    # url='https://gateway.watsonplatform.net/tone-analyzer/api'
)

def post_list(request, tag_slug=None):
    object_list = Post.published.all()
    tag = None

    kk = Post.objects.filter(publish__lte=timezone.now()).order_by('publish')

    for post in kk:
        posting = post.body
        translation = language_translator.translate(
            text=post.body, model_id='en-es').get_result()
        obj = (json.dumps(translation, indent=2, ensure_ascii=False))
        #print(obj)
        obj2 = json.loads(obj)
        post.obj2 = obj2['translations'][0]['translation']
        post.w_count = obj2['word_count']
        post.c_count = obj2['character_count']
        print("post.w_count",post.w_count)
        print("post.c_count", post.c_count)
        tone_input = ToneInput(post.body)
        try:
            tone = tone_analyzer.tone(tone_input=tone_input, content_type="application/json").get_result()
            jsonText = (json.dumps(tone, indent=2, ensure_ascii=False))
            jsonParse = json.loads(jsonText)
            post.Score1 = jsonParse['document_tone']['tones'][0]['score']
            post.ToneName1 = jsonParse['document_tone']['tones'][0]['tone_name']
        except:
            pass
            post.Score1 = "no-data value for key Score from API response"
            post.ToneName1 = "no-data value for key ToneName from API response"
            print("OOPS! Something went wrong while rendering the Document tone json")
        print("Score",post.Score1)
        print("tone",post.ToneName1)

    if tag_slug:
         tag = get_object_or_404(Tag, slug=tag_slug)
         object_list = object_list.filter(tags__in=[tag])

    paginator = Paginator(object_list, 3)  # 3 posts in each page
    page = request.GET.get('page')
    try:
        posts = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer deliver the first page
        posts = paginator.page(1)
    except EmptyPage:
        # If page is out of range deliver last page of results
        posts = paginator.page(paginator.num_pages)

    return render(request,
                  'blog/post_list.html',
                  {'page': page,
                   'posts': kk,
                   'tag': tag})

class PostListView(ListView):
    queryset = Post.published.all()
    context_object_name = 'posts'
    paginate_by = 3
    template_name = 'blog/post_list.html'

@login_required()
def post_edit(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if request.method == "POST":
        form = PostForm(request.POST, instance=post)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.published_date = timezone.now()
            post.save()
            return redirect('blog:post_list' )
    else:
        form = PostForm(instance=post)
    return render(request, 'blog/post_edit.html', {'form': form})

def post_share(request, post_id):
    # Retrieve post by id
    post = get_object_or_404(Post, id=post_id, status='published')
    sent = False

    if request.method == 'POST':
        # Form was submitted
        form = EmailPostForm(request.POST)
        if form.is_valid():
            # Form fields passed validation
            cd = form.cleaned_data
            post_url = request.build_absolute_uri(
                post.get_absolute_url())
            subject = '{} ({}) recommends you reading "{}"'.format(cd['name'], cd['email'], post.title)
            message = 'Read "{}" at {}\n\n{}\'s comments: {}'.format(post.title, post_url, cd['name'], cd['comments'])
            send_mail(subject, message, 'admin@myblog.com',
                      [cd['to']])
            sent = True
    else:
        form = EmailPostForm()
    return render(request, 'blog/share.html', {'post': post,
                                                    'form': form,
                                                    'sent': sent})

def post_detail(request, year, month, day, post):
    post = get_object_or_404(Post, slug=post,
                             status='published',
                             publish__year=year,
                             publish__month=month,
                             publish__day=day)

    # List of active comments for this post
    comments = post.comments.filter(active=True)

    new_comment = None

    if request.method == 'POST':
        # A comment was posted
        comment_form = CommentForm(data=request.POST)
        if comment_form.is_valid():
            # Create Comment object but don't save to database yet
            new_comment = comment_form.save(commit=False)
            # Assign the current post to the comment
            new_comment.post = post
            # Save the comment to the database
            new_comment.save()
    else:
        comment_form = CommentForm()

    # List of similar posts
    post_tags_ids = post.tags.values_list('id', flat=True)
    similar_posts = Post.published.filter(tags__in=post_tags_ids) \
        .exclude(id=post.id)
    similar_posts = similar_posts.annotate(same_tags=Count('tags')) \
                        .order_by('-same_tags', '-publish')[:4]

    return render(request,
                  'blog/post_detail.html',
                  {'post': post,
                   'comments': comments,
                   'new_comment': new_comment,
                   'comment_form': comment_form,
                   'similar_posts': similar_posts})

@login_required()
def post_new(request):
    if request.method == "POST":
        form = PostForm(request.POST)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.published_date = timezone.now()
            post.save()
            return redirect('blog:post_list')
    else:
        form = PostForm()
    return render(request, 'blog/post_edit.html', {'form': form})