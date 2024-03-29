"""
Definition of views.
"""

import operator
import random
from random import shuffle
import datetime
from django.shortcuts import render, redirect
from django.http import HttpRequest, Http404, HttpResponse
from django.template import RequestContext
from datetime import datetime
from app.forms import *
from django.contrib.auth import authenticate as auth_authenticate
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db import transaction
from django.db.models import Q
from django.contrib import messages
from django.contrib.auth.hashers import PBKDF2PasswordHasher as hasher
from django.contrib.auth.hashers import make_password
from time import sleep
from yelpapi import YelpAPI
import argparse
from pprint import pprint
from django.conf import settings
import json
from django.core.cache import cache
from django.core.paginator import Paginator
from django import template
import ast #literal evaluation

registerT = template.Library()
yelp_api = YelpAPI(settings.API_KEY, timeout_s=3.0)

"""
View helper functions
"""

# Working around the deprecation of request.is_ajax()
def is_ajax(request):
    return request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest'

def get_cached_business(id):
    if cache.get(str(id)):
        print("Using cached results!")
        raw_data = cache.get(str(id))
        data = json.loads(json.dumps(raw_data))
        return data
    else:
        print("Business is not cached!")
        return None

def get_confidence_score(user, business):
    if business['id'] in user.dislikes[:-1].split(','):
        return -1.0
    
    tastes = ast.literal_eval(user.tastes)
    confidence = 0
    total = 0

    for cat in business['categories']:
        total += 1
        if cat['title'] in tastes:
            confidence += 1
    
    return float(confidence / total)

def add_confidence_scores(user, businesses):
    confidence_sum = 0.0
    total = 0.0
    confidence_score = 0.0

    try:
        for business in businesses:
            if business:
                business['confidence_score'] = get_confidence_score(user, business)
    except:
        businesses = []

    return businesses

def get_init_states(page, user, businesses, votes):
    try:
        if page == 'vote':
            for business in businesses:
                business['init_up'] = votes[0][business['id']]
                business['init_down'] = votes[1][business['id']]

        else:
            for business in businesses:
                if business['id'] in user.stars[:-1].split(','):
                    business['init_star'] = True
                else:
                    business['init_star'] = False
                if business['id'] in user.likes[:-1].split(','):
                    business['init_like'] = True
                else:
                    business['init_like'] = False
                if business['id'] in user.dislikes[:-1].split(','):
                    business['init_dislike'] = True
                else:
                    business['init_dislike'] = False
    except:
        businesses = []

    return businesses

def get_yelp_results(query,location,radius,sortby,pricerange,opennow,attributes):
    if cache.get(''.join(i for i in str(query+location+radius+sortby+pricerange+opennow) if i.isalnum())):
        print("Using cached results!")
        print(''.join(i for i in str(query+location+radius+sortby+pricerange+opennow) if i.isalnum()))
        raw_data = cache.get(''.join(i for i in str(query+location+radius+sortby+pricerange+opennow) if i.isalnum()))
        
        data = json.loads(json.dumps(raw_data))
    else:
        print("Querying Yelp Fusion API")
        raw_data = yelp_api.search_query(term=query,
                                         location=location,
                                         radius=radius,
                                         limit=48,
                                         sort_by=sortby,
                                         price=pricerange,
                                         open_now=opennow,
                                         attributes=attributes)
            
        data = json.loads(json.dumps(raw_data))
        cache.set(''.join(i for i in str(query+location+radius+sortby+pricerange+opennow) if i.isalnum()), data, 86400)  #TODO: Use DEFAULT_TIMEOUT'

    # Cache businesses
    for b in data['businesses']:
        cache.set(b['id'], b, 2592000)  #TODO: Use DEFAULT_TIMEOUT

    return data

def user_function(user, data, query, location):
    words = []
    tmp_words = {}

    if user:
        try:
            cached_data = cache.get(user.username + '_searches')
            if not cached_data:
                cached_data = {}
        except:
            cached_data = {}

    try:
        cached_data_all = cache.get('all_searches')
        if not cached_data_all:
            cached_data_all = {}
    except:
        cached_data_all = {}

    if user:
        if query in cached_data:
            cached_data[query] += 1
        else:
            cached_data[query] = 1
        
    if query in cached_data_all:
        cached_data_all[query] += 1
    else:
        cached_data_all[query] = 1

    if user:
        data['businesses'] = add_confidence_scores(user, data['businesses'])
        data['businesses'] = get_init_states('search', user, data['businesses'], None)

        cache.set(user.username + 'location', location, 2592000) # 30 days
        cache.set(user.username + '_searches', cached_data, 2592000) # 30 days

        max_search = max(cached_data.items(), key=operator.itemgetter(1))[1]

        for w, v in cached_data.items():
            word = {}
            tmp_words[w] = True
            word['text'] = w.lower()
            word['weight'] = int(12 * (v / max_search))
            word['link'] = 'search/?q=' + w + '&loc=' + location + '&rad=8050&sort=best_match&price=1,2,3,4&open=false'
            words.append(word)


    max_search_all = max(cached_data_all.items(), key=operator.itemgetter(1))[1]

    for w, v in cached_data_all.items():
        if not w in tmp_words:
            word = {}
            word['text'] = w.lower()
            word['weight'] = int(6 * (v / max_search_all))
            word['link'] = 'search/?q=' + w + '&loc=' + location + '&rad=8050&sort=best_match&price=1,2,3,4&open=false'
            words.append(word)

    cache.set('all_searches', cached_data_all, 2592000) # 30 days

    return data, words


"""
Ajax functions
"""

@login_required
@require_POST
@csrf_exempt
def addopt(request):
    if request.method == 'POST':
        raw_data = request.body.decode('utf-8')
        data = json.loads(raw_data)
        vote_opt = VoteOption()
        print("Data: ", data)
        group_vote = GroupVote.objects.get(data['vote_name'])
        # vote_opt.group_vote_id = data['vote_name']
        print("Retrieved Group Vote: ", group_vote)
        vote_opt.group_vote = group_vote
        vote_opt.opt_id = data['element_id']
        vote_opt.business_id = data['element_id']
        vote_opt.upvotes = ''
        vote_opt.downvotes = ''
        vote_opt.save()
        response = {'success':True}
    return HttpResponse(json.dumps(response), content_type='application/json')

@login_required
@require_POST
@csrf_exempt
def dislike(request):
    if request.method == 'POST':
        raw_data = request.body.decode('utf-8')
        data = json.loads(raw_data)
        user = request.user
        business_id = data['element_id'][:-2]

        if business_id in user.dislikes[:-1].split(','):
            user.dislikes = user.dislikes.replace(business_id + ',', '')
            sel = '#' + data['element_id']
            response = {'success': False, 'element_id': sel}
        else:
            user.dislikes += business_id + ','
            sel = '#' + data['element_id']
            if business_id in user.likes[:-1].split(','):
                user.likes = user.likes.replace(business_id + ',', '')
                response = {'success': True, 'toggled': True, 'element_toggled': sel[:-2] + 'tu', 'element_id': sel}
            else:
                response = {'success': True, 'toggled': False, 'element_id': sel}
        user.save()

    return HttpResponse(json.dumps(response), content_type='application/json')

@login_required
@require_POST
@csrf_exempt
def like(request):
    if request.method == 'POST':
        raw_data = request.body.decode('utf-8')
        data = json.loads(raw_data)
        user = request.user
        business_id = data['element_id'][:-2]
        tastes = ast.literal_eval(user.tastes)

        if business_id in user.likes[:-1].split(','):
            for cat in data['categories'][:-1].split(','):
                if tastes[cat] == 1:
                    del tastes[cat]
                else:
                    tastes[cat] -= 1

            user.likes = user.likes.replace(business_id + ',', '')
            user.tastes = str(tastes)

            sel = '#' + data['element_id']
            response = {'success': False, 'element_id': sel}
        else:
            for cat in data['categories'][:-1].split(','):
                if cat in tastes:
                    tastes[cat] += 1
                else:
                    tastes[cat] = 1

            user.likes += business_id + ','
            user.tastes = str(tastes)

            sel = '#' + data['element_id']
            if business_id in user.dislikes[:-1].split(','):
                user.dislikes = user.dislikes.replace(business_id + ',', '')
                response = {'success': True, 'toggled': True, 'element_toggled': sel[:-2] + 'td', 'element_id': sel}
            else:
                response = {'success': True, 'toggled': False, 'element_id': sel}
        user.save()

    return HttpResponse(json.dumps(response), content_type='application/json')

@login_required
@require_POST
@csrf_exempt
def star(request):
    if request.method == 'POST':
        raw_data = request.body.decode('utf-8')
        data = json.loads(raw_data)
        user = request.user
        business_id = data['element_id'][:-2]

        if business_id in user.stars[:-1].split(','):
            user.stars = user.stars.replace(business_id + ',', '')
            sel = '#' + data['element_id']
            response = {'success': False, 'element_id': sel}
        else:
            user.stars += business_id + ','
            sel = '#' + data['element_id']
            if business_id in user.dislikes[:-1].split(','):
                user.dislikes = user.dislikes.replace(business_id + ',', '')
                response = {'success': True, 'toggled': True, 'element_toggled': sel[:-2] + 'td', 'element_id': sel}
            else:
                response = {'success': True, 'toggled': False, 'element_id': sel}
        user.save()

    return HttpResponse(json.dumps(response), content_type='application/json')

def cast_vote(user, data, vote_opt, type, vote_name, element_id):
    group_vote = GroupVote.objects.get(vote_opt.group_vote_id)
    vote_counts = []
    business_names = []

    if type == 0:
        votes_pri = vote_opt.downvotes
        votes_sec = vote_opt.upvotes
        pri = 'vd'
        sec = 'vu'
    else:
        votes_pri = vote_opt.upvotes
        votes_sec = vote_opt.downvotes
        pri = 'vu'
        sec = 'vd'

    if user.username in votes_pri[:-1].split(','):
        votes_pri = votes_pri.replace(user.username + ',', '')
        sel = '#' + element_id
        response = {'success': False, 'element_id': sel}
    else:
        votes_pri += user.username + ','
        sel = '#' + element_id
        if user.username in votes_sec[:-1].split(','):
            votes_sec = votes_sec.replace(user.username + ',', '')
            response = {'success': True, 'toggled': True, 'element_toggled': sel + sec, 'element_id': sel + pri}
        else:
            response = {'success': True, 'toggled': False, 'element_id': sel + pri}

    if type == 0:
        vote_opt.downvotes = votes_pri
        vote_opt.upvotes = votes_sec
    else:
        vote_opt.upvotes = votes_pri
        vote_opt.downvotes = votes_sec
    vote_opt.save()

    vote_options = GroupVote.objects.get_options(group_vote.vote_id)
    for vo in vote_options:
        vo_count = VoteOption.objects.vote_count(vo.opt_id)
        business = get_cached_business(vo.business_id)
        business_names.append(business['name'])
        vote_counts.append(vo_count)

    response["chart_labels"] = business_names
    response["chart_data"] = vote_counts

    return response

@login_required
@require_POST
@csrf_exempt
def downvote(request):
    if request.method == 'POST':
        raw_data = request.body.decode('utf-8')
        data = json.loads(raw_data)
        print('Downvote data: ', data)
        user = request.user
        vote_opt = VoteOption.objects.get(data['vote_name'], data['element_id'][:-2])

        response = cast_vote(user, data, vote_opt, 0, data['vote_name'], data['element_id'][:-2])

    return HttpResponse(json.dumps(response), content_type='application/json')

@login_required
@require_POST
@csrf_exempt
def upvote(request):
    if request.method == 'POST':
        raw_data = request.body.decode('utf-8')
        data = json.loads(raw_data)
        print('Upvote data: ', data)
        user = request.user
        vote_opt = VoteOption.objects.get(data['vote_name'], data['element_id'][:-2])

        response = cast_vote(user, data, vote_opt, 1, data['vote_name'], data['element_id'][:-2])

    return HttpResponse(json.dumps(response), content_type='application/json')

@login_required
@require_POST
@csrf_exempt
def update_chart(request):
    if request.method == 'POST':
        raw_data = request.body.decode('utf-8')
        data = json.loads(raw_data)
        if data:
            user = request.user
            print(f"Data: {data}")
            group_vote = GroupVote.objects.get(data['vote_name'])
            vote_counts = []
            business_names = []

            print(f"Getting vote options for {group_vote.vote_id}")
            vote_options = GroupVote.objects.get_options(group_vote.vote_id)
            for vo in vote_options:
                vo_count = VoteOption.objects.vote_count(vo.opt_id)
                business = get_cached_business(vo.business_id)
                business_names.append(business['name'])
                vote_counts.append(vo_count)

            response = {'success': True, 'chart_labels': business_names, 'chart_data': vote_counts}
        else:
            response = {'success': False}

    return HttpResponse(json.dumps(response), content_type='application/json')


"""
Django page views
"""

@login_required
def create_group(request):
    """Renders the create group page."""
    print("Create Group View")
    time_form = CustomTimeForm()

    if request.method == 'POST':
        print("Create Group: POST Request")
        form = CustomGroupCreationForm(data=request.POST)
        if form.is_valid():
            print("Create Group: Form Valid")
            group, created = Group.objects.get_or_create(name=form.cleaned_data['name'])
            user = request.user
            cgroup = CustomGroup.objects.create(form.cleaned_data['name'], group.id)
            user = request.user
            if created:
                user.groups.add(group)
                group.save()
                messages.success(request, 'Your group was successfully created!')
            return redirect('group/?g=' + group.name)
        else:
            print("Create Group: Form Invalid")
            print(form.errors)
            messages.error(request, 'Please correct the error below.')
    else:
        print("Register: GET Request")
        form = CustomGroupCreationForm()
    assert isinstance(request, HttpRequest)
    return render(
        request,
        'app/create_group.html',
        {
            'title': 'Create Group',
            'form': form,
            'time_form': time_form,
        }
    )

@login_required
def create_group_vote(request):
    """Renders the create vote page."""
    print("Create Vote View")
    time_form = CustomTimeForm()

    if request.method == 'POST':
        print("Create Vote: POST Request")
        form = CustomVoteCreationForm(data=request.POST)
        if form.is_valid():
            print("Create Vote: Form Valid")
            groupname = request.GET.get('g', None)
            group = Group.objects.get(name = groupname)
            cgroup = CustomGroup.objects.get(group.id)
            vote_id = str(group.id) + datetime.datetime.now().strftime("--%m-%d-%y--") + form.cleaned_data["name"]
            name = datetime.datetime.now().strftime("(%m-%d-%y)  ") + form.cleaned_data["name"]
            print(f"Data: {(vote_id, name, cgroup)}")
            group_vote, created = GroupVote.objects.get_or_create(vote_id, name, cgroup)
            if created:
                messages.success(request, 'Your vote was successfully created!')
            else:
                messages.error(request, "Vote creation failed!")
            return redirect('group/vote/?g=' + group.name + '&v=' + group_vote.vote_id)
        else:
            print("Create Vote: Form Invalid")
            print(form.errors)
            messages.error(request, 'Please correct the error below.')
    else:
        print("Create Vote: GET Request")
        form = CustomVoteCreationForm()
        groupname = request.GET.get('g', None)
        group = Group.objects.get(name = groupname)
    assert isinstance(request, HttpRequest)
    return render(
        request,
        'app/create_group_vote.html',
        {
            'title': 'Create Vote',
            'form': form,
            'time_form': time_form,
            'group': group,
        }
    )

@login_required
def group(request):
    """Renders the group page.
        TODO: Implement
    """
    print("Group View")
    time_form = CustomTimeForm()
    active_votes = {}

    if request.method == 'GET':
        print("Group: GET Request")
        form = CustomGroupChangeForm()
        groupname = request.GET.get('g', None)

        if 'g' in request.GET:
            print(request.GET)
        else:
            print('g not found!')

        group = Group.objects.get(name = groupname)
        cgroup = CustomGroup.objects.get(group.id)
        users = CustomUser.objects.filter(groups__name=groupname)
    else:
        print("Group: POST Request")
        form = CustomGroupChangeForm(data=request.POST)
        if form.is_valid():
            print("Group: Form Valid")
            if form.cleaned_data['act'] == 'add':
                group = Group.objects.get(name = form.cleaned_data['grp'])
                cgroup = CustomGroup.objects.get(group.id)
                user = CustomUser.objects.get(username = form.cleaned_data['usr'])
                if user.groups.filter(name=group.name).exists():
                    messages.error(request, 'User is already a member.')
                else:
                    user.groups.add(group)
                    group.save()
                users = CustomUser.objects.filter(groups__name=group.name)
            elif form.cleaned_data['act'] == 'rem':
                group = Group.objects.get(name = form.cleaned_data['grp'])
                cgroup = CustomGroup.objects.get(group.id)
                user = CustomUser.objects.get(username = form.cleaned_data['usr'])
                user.groups.remove(group)
                users = CustomUser.objects.filter(groups__name=group.name)
                
                if len(users) == 0:
                    return redirect('group')
                group.save()
            else:
                print('Error: unknown action')
                group = Group()
                cgroup = CustomGroup()
                users = []

            messages.success(request, 'Your group action was successful!')
    
    v_all = GroupVote.objects.all_active(cgroup.name)
    for v in v_all:
        active_votes.update({v.vote_id: v.name})

    assert isinstance(request, HttpRequest)
    return render(
        request,
        'app/group.html',
        {
            'title': 'Group',
            'time_form': time_form,
            'form': form,
            'group': group,
            'users': users,
            'active_votes': active_votes,
        }
    )

@login_required
def group_manage(request):
    """Renders the group page.
        TODO: Implement
    """
    print("Group View")
    time_form = CustomTimeForm()

    if request.method == 'GET':
        print("Group: GET Request")
        form = CustomGroupChangeForm()
        groupname = request.GET.get('g', None)

        if 'g' in request.GET:
            print(request.GET)
        else:
            print('g not found!')

        group = Group.objects.get(name = groupname)
        users = CustomUser.objects.filter(groups__name=groupname)
    else:
        print("Group: POST Request")
        form = CustomGroupChangeForm(data=request.POST)
        if form.is_valid():
            print("Group: Form Valid")
            if form.cleaned_data['act'] == 'add':
                group = Group.objects.get(name = form.cleaned_data['grp'])
                user = CustomUser.objects.get(username = form.cleaned_data['usr'])
                if user.groups.filter(name=group.name).exists():
                    messages.error(request, 'User is already a member.')
                else:
                    user.groups.add(group)
                    group.save()
                users = CustomUser.objects.filter(groups__name=group.name)
            elif form.cleaned_data['act'] == 'rem':
                group = Group.objects.get(name = form.cleaned_data['grp'])
                user = CustomUser.objects.get(username = form.cleaned_data['usr'])
                user.groups.remove(group)
                users = CustomUser.objects.filter(groups__name=group.name)
                
                if len(users) == 0:
                    return redirect('group')
                group.save()
            else:
                print('Error: unknown action')
                group = ''
                users = []

            messages.success(request, 'Your group action was successful!')
        

    assert isinstance(request, HttpRequest)
    return render(
        request,
        'app/group_manage.html',
        {
            'title': 'Group',
            'time_form': time_form,
            'form': form,
            'group': group,
            'users': users,
        }
    )

@login_required
def group_vote(request):
    """Renders the group vote page."""
    print("Create Group View")
    time_form = CustomTimeForm()
    data = []

    if request.method == 'POST':
        print("Create Group: POST Request")
    else:
        print("Register: GET Request")
        groupname = request.GET.get('g', None)
        groupvoteid = request.GET.get('v', None)
        user = request.user
        group = Group.objects.get(name=groupname)
        cgroup = CustomGroup.objects.get(group.id)
        # Convert name to vote ID
        if groupvoteid:
            groupvoteid = groupvoteid.replace('(', '-').replace(')  ', '--')
        group_vote = GroupVote.objects.get(groupvoteid)
        vote_options = GroupVote.objects.get_options(groupvoteid)
        votes = [{},{}]

        for opt in vote_options:
            business = get_cached_business(opt.business_id)
            if business:
                data.append(business)
                votes[0][opt.business_id] = user.username in opt.upvotes[:-1].split(',')
                votes[1][opt.business_id] = user.username in opt.downvotes[:-1].split(',')
            
        data = add_confidence_scores(user, data)
        data = get_init_states('vote', user, data, votes)

        results_page = request.GET.get('page', 1)
        paginator = Paginator(data, 4)
        pages = paginator.page_range

        results = paginator.page(results_page)
    assert isinstance(request, HttpRequest)
    return render(
        request,
        'app/group_vote.html',
        {
            'title':'Create Group',
            #'form':form,
            'time_form': time_form,
            'pages': pages,
            'group': group,
            'group_vote': group_vote,
            'results': results,
        }
    )

def home(request):
    """Renders the home page.
        TODO: Implement
    """
    print("Home View")
    time_form = CustomTimeForm()
    active_votes = {}
    words = []

    if request.user.is_authenticated:
        location = cache.get(request.user.username + 'location')

    else:
        location = "Irvine, CA"

    if request.method == 'GET':
        query = 'food'
        location = 'Irvine, CA'
        radius = '16100'
        sortby = 'rating'
        pricerange = '1,2,3,4'
        opennow = 'false'
        attributes = 'hot_and_new'

        data = get_yelp_results(query,location,radius,sortby,pricerange,opennow,attributes)

        if request.user.is_authenticated:
            user = request.user
            data, words = user_function(user, data, query, location)

            # Remove disliked businesses
            data['businesses'] = [business for business in data['businesses'] if business['id'] not in user.dislikes[:-1].split(',')]

            for g in user.groups.all():
                v_all = GroupVote.objects.all_active(g.name)
                for v in v_all:
                    active_votes.update({v.vote_id: v.name})
                    
        else:
            user = None
            data, words = user_function(None, data, query, location)

        shuffle(data['businesses'])

        results_page = request.GET.get('page', 1)
        paginator = Paginator(data['businesses'], 2)
        pages = []

        results = paginator.page(results_page)

        print("Home: GET Request")
        context = {'title':'Home',
                   'results':results,
                   'query':'',
                   'location':'Irvine, CA',
                   'time_form': time_form,
                   'pages': pages,
                   'user': user,
                   'active_votes': active_votes,
                   'words': words,
                   }

        assert isinstance(request, HttpRequest)
        return render(
            request,
            'app/home.html',
            context)

    else:
        return render(request,"app/home.html",{})

def login(request):
    """Renders the login page."""
    print("Login View")
    time_form = CustomTimeForm()

    if request.method == 'POST':
        print("Login: POST Request")
        form = CustomUserAuthenticationForm(data=request.POST)
        if form.is_valid():
            print("Login: Form Valid")
            user = auth_authenticate(username=request.POST['username'].lower(),
                                     password=request.POST['password'])
            auth_login(request,user)
            print(request.user.last_login)
            return redirect('/')
        else:
            print("Login: Form Invalid")
            print(form.errors)
            messages.error(request, 'Please correct the error below.')
    else:
        print("Login: GET Request")
        form = CustomUserAuthenticationForm()
    assert isinstance(request, HttpRequest)
    return render(
        request,
        'app/login.html',
        {
            'title':'Login',
            'form': form,
            'time_form': time_form,
        }
    )

def logout(request):
    auth_logout(request)
    return redirect('/')

@login_required
def password(request):
    """Renders the edit account info page.
        TODO: Implement changing password
    """
    print("Password View")
    time_form = CustomTimeForm()

    if request.method == 'POST':
        print("Password: POST Request")
        form = CustomPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.add_message(request, messages.INFO, 'Password changed.')
            return redirect('password')
        else:
            print("Password: Form Invalid")
            print(form.errors)
            messages.error(request, 'Please correct the error below.')
    else:
        print("Password: GET Request")
        form = CustomPasswordChangeForm(request.user)
    assert isinstance(request, HttpRequest)
    return render(
        request,
        'app/password.html',
        {
            'title':'Password',
            'form':form,
            'time_form': time_form,
        }
    )

@login_required
def profile(request):
    """Renders the user profile info page.
        TODO: Implement
    """
    print("User Profile View")
    time_form = CustomTimeForm()
    groups = []
    stars = []
    likes = []
    dislikes = []

    if request.method == 'GET':
        print("User Profile: GET Request")
        name = request.GET.get('u', None)

        if 'u' in request.GET:
            print(request.GET)
        else:
            print('u not found!')
    else:
        print("User Profile: POST Request")
        name = ""

    user = CustomUser.objects.get(username = name)
    for g in user.groups.all():
        groups.append(g.name)
    for s in user.stars[:-1].split(','):
        business = get_cached_business(s)
        if business:
            stars.append({'name': business['name'], 'link': business['url']})
    for l in user.likes[:-1].split(','):
        business = get_cached_business(l)
        if business:
            likes.append({'name': business['name'], 'link': business['url']})
    for d in user.dislikes[:-1].split(','):
        business = get_cached_business(d)
        if business:
            dislikes.append({'name': business['name'], 'link': business['url']})

    assert isinstance(request, HttpRequest)
    return render(
        request,
        'app/profile.html',
        {
            'title':'Profile',
            'time_form': time_form,
            'profile': user,
            'groups': groups,
            'stars': stars,
            'likes': likes,
            'dislikes': dislikes,
        }
    )

def randomizer(request):
    """Renders the randomizer page.
        TODO: Implement
    """
    print("Randomizer View")
    time_form = CustomTimeForm()
    rindex = 0

    if request.method == 'GET':
        query = request.GET.get('q', None)
        location = request.GET.get('loc', None)
        radius = request.GET.get('rad', None)
        sortby = request.GET.get('sort', None)
        pricerange = request.GET.get('price', None)
        opennow = request.GET.get('open', None)

        if 'q' in request.GET:
            print(request.GET)
        else:
            print('q not found!')

        if 'loc' in request.GET:
            print(request.GET)
        else:
            print('loc not found!')

        if 'rad' in request.GET:
            print(request.GET)
        else:
            print('rad not found!')

        if 'sort' in request.GET:
            print(request.GET)
        else:
            print('sort not found!')

        if 'price' in request.GET:
            print(request.GET)
        else:
            print('price not found!')

        if 'open' in request.GET:
            print(request.GET)
        else:
            print('open not found!')

        if cache.get(''.join(i for i in str(query+location+radius+sortby+pricerange+opennow) if i.isalnum())):
            print("Using cached results!")
            print(''.join(i for i in str(query+location+radius+sortby+pricerange+opennow) if i.isalnum()))
            raw_data = cache.get(''.join(i for i in str(query+location+radius+sortby+pricerange+opennow) if i.isalnum()))
        else:
            print("Querying Yelp Fusion API")
            raw_data = yelp_api.search_query(term=query,
                                             location=location,
                                             radius=radius,
                                             limit=48,
                                             sort_by=sortby,
                                             price=pricerange,
                                             open_now=opennow)
            
        data = json.loads(json.dumps(raw_data))
        cache.set(''.join(i for i in str(query+location+radius+sortby+pricerange+opennow) if i.isalnum()), data, 86400)  #TODO: Use DEFAULT_TIMEOUT

        shuffle(data['businesses'])

        results = [data['businesses'][0]]

        print(results)

        print("Random: GET Request")
        context = {'title':'Randomizer',
                   'results':results,
                   'query':query,
                   'location':location,
                   'time_form': time_form,
                   'messages': messages,
                   }

        assert isinstance(request, HttpRequest)
        return render(
            request,
            'app/random.html',
            context)

    else:
        return render(request,"app/random.html",{})

def register(request):
    """Renders the register page."""
    print("Register View")
    time_form = CustomTimeForm()

    if request.method == 'POST':
        print("Register: POST Request")
        form = CustomUserCreationForm(data=request.POST)
        if form.is_valid():
            print("Register: Form Valid")
            form.save()
            new_user = auth_authenticate(username=form.cleaned_data['username'],
                                    password=form.cleaned_data['password1'],
                                    )
            auth_login(request, new_user)
            messages.success(request, 'Your account was successfully created!')
            return redirect('/')
        else:
            print("Register: Form Invalid")
            print(form.errors)
            messages.error(request, 'Please correct the error below.')
    else:
        print("Register: GET Request")
        form = CustomUserCreationForm()
    assert isinstance(request, HttpRequest)
    return render(
        request,
        'app/register.html',
        {
            'title':'Register',
            'form':form,
            'time_form': time_form,
        }
    )

def search(request):
    """Renders the search page.
        TODO: Update content
    """
    print("Search View")
    time_form = CustomTimeForm()
    active_votes = {}
    words = []

    if request.method == 'GET':
        query = request.GET.get('q', None)
        location = request.GET.get('loc', None)
        radius = request.GET.get('rad', None)
        sortby = request.GET.get('sort', None)
        pricerange = request.GET.get('price', None)
        opennow = request.GET.get('open', None)

        data = get_yelp_results(query,location,radius,sortby,pricerange,opennow,"")

        if request.user.is_authenticated:
            user = request.user
            data, words = user_function(user, data, query, location)

            # Remove disliked businesses
            data['businesses'] = [business for business in data['businesses'] if business['id'] not in user.dislikes[:-1].split(',')]

            for g in user.groups.all():
                v_all = GroupVote.objects.all_active(g.name)
                for v in v_all:
                    active_votes.update({v.vote_id: v.name})

        results_page = request.GET.get('page', 1)
        paginator = Paginator(data['businesses'], 12)
        pages = paginator.page_range

        results = paginator.page(results_page)

        print("Settings: GET Request")
        context = {'title':'Search',
                   'results':results,
                   'query':query,
                   'location':location,
                   'radius': radius,
                   'sortby': sortby,
                   'pricerange': pricerange,
                   'opennow': opennow,
                   'time_form': time_form,
                   'pages': pages,
                   'group': group,
                   'active_votes': active_votes,
                   'words': words,
                   }

        assert isinstance(request, HttpRequest)
        return render(
            request,
            'app/search.html',
            context)

    else:
        return render(request,"app/search.html",{})

@login_required
def settings(request):
    """Renders the edit account info page.
        TODO: Implement changing account information
    """
    print("Settings View")
    time_form = CustomTimeForm()

    if request.method == 'POST':
        print("Settings: POST Request")
        form = CustomUserChangeForm(instance=request.user, data=request.POST)
        if form.is_valid():
            form.save()
            messages.add_message(request, messages.INFO, 'Settings changed.')
            return redirect('settings')
        else:
            print("Settings: Form Invalid")
            print(form.errors)
            messages.error(request, 'Please correct the error below.')
    else:
        print("Settings: GET Request")
        form = CustomUserChangeForm(instance=request.user)
    assert isinstance(request, HttpRequest)
    return render(
        request,
        'app/settings.html',
        {
            'title':'Settings',
            'form':form,
            'time_form': time_form,
        }
    )

def suggestions(request):
    """Renders the suggestions page.
        TODO: Update content
    """
    print("Suggestions View")
    time_form = CustomTimeForm()
    active_votes = {}
    words = []
    
    if request.user.is_authenticated:
        location = cache.get(request.user.username + 'location')
    else:
        location = "Irvine, CA"

    if request.method == 'GET':
        query = 'food'
        location = 'Irvine, CA'
        radius = '16100'
        sortby = 'rating'
        pricerange = '1,2,3,4'
        opennow = 'false'
        attributes = 'rating'

        data = {'businesses': []}
        
        if request.user.is_authenticated:
            user = request.user

            for s in user.stars[:-1].split(','):
                star = get_cached_business(s)
                data['businesses'].append(star)

            data, words = user_function(user, data, query, location)

            for g in user.groups.all():
                v_all = GroupVote.objects.all_active(g.name)
                for v in v_all:
                    active_votes.update({v.vote_id: v.name})
        else:
            user = None

        results_page = request.GET.get('page', 1)
        paginator = Paginator(data['businesses'], 12)
        pages = paginator.page_range

        results = paginator.page(results_page)

        print("Suggestions: GET Request")
        context = {'title':'Suggestions',
                   'results':results,
                   'query':'',
                   'location':'Irvine, CA',
                   'time_form': time_form,
                   'pages': pages,
                   'user': user,
                   'active_votes': active_votes,
                   'words': words,
                   }

        assert isinstance(request, HttpRequest)
        return render(
            request,
            'app/search.html',
            context)

    else:
        return render(request,"app/search.html",{})

@login_required
def voting(request):
    """Renders the vote page.
        TODO: Implement
    """
    print("Vote View")
    time_form = CustomTimeForm()
    groups = []

    
    user = CustomUser.objects.get(username = request.user.username)
    for g in user.groups.all():
        groups.append(g.name)

    assert isinstance(request, HttpRequest)
    return render(
        request,
        'app/voting.html',
        {
            'title':'Group Vote Page',
            'time_form': time_form,
            'groups': groups,
        }
    )

@login_required
def user_autocomplete(request):
    if is_ajax(request):
        if 'term' in request.GET:
            print(request.GET)
            q = request.GET.get('term', '')

            print("Querying Database for Users")
            raw_data = CustomUser.objects.all()
            users = []

            for u in raw_data:
                if u.username.startswith(q):
                    users.append(u.username)
            
            data = json.dumps(users)
        else:
            print('term not found!')
    return HttpResponse(data, 'application/json')

def yelp_autocomplete(request):
    if is_ajax(request):
        if 'term' in request.GET:
            print(request.GET)
            q = request.GET.get('term', '').capitalize()

            if cache.get(''.join(i for i in str('autoc-'+q) if i.isalnum())):
                print("Using cached autocomplete results!")
                print(''.join(i for i in str('autoc-'+q) if i.isalnum()))
                data = cache.get(''.join(i for i in str('autoc-'+q) if i.isalnum()))
            else:
                print("Querying Yelp Fusion Autocomplete API")
                raw_data = yelp_api.autocomplete_query(text=q)
                autoc_results = []

                if len(raw_data['terms']) > 0:
                    for t in raw_data['terms']:
                        autoc_results.append(t['text'])
                if len(raw_data['businesses']) > 0:
                    for b in raw_data['businesses']:
                        if c['text']:
                            autoc_results.append(c['text'])
                        elif c['name']:
                            autoc_results.append(c['name'])
                if len(raw_data['categories']) > 0:
                    for c in raw_data['categories']:
                        autoc_results.append(c['title'])
                data = json.dumps(autoc_results)
                cache.set(''.join(i for i in str('autoc-'+q) if i.isalnum()), data, 86400)
        else:
            print('term not found!')
    return HttpResponse(data, 'application/json')

@staff_member_required
@login_required
def delete_user(request, username):
    """Delete user view (NO TEMPLATE)
        TODO: Actually delete users
    """

    context = {}

    try:
        username = request.GET.get('u', '')
        user = CustomUser.objects.get(username = username)
        user.delete()
        context['msg'] = 'The user is deleted.'            

    except CustomUser.DoesNotExist:
        messages.error(request, "User does not exist")

    return render(request, 'home.html', context=context)