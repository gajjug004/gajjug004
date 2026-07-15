"""Recalculate the stats on the profile README and write them into the SVG cards.

Based on Andrew6rant/Andrew6rant, with his personal bits (a hardcoded owner id, an archive
of his deleted repositories) removed and two bugs fixed -- see svg_overwrite().

Needs two repository secrets:
  ACCESS_TOKEN  fine-grained PAT, all repositories
                account:      read Followers, Starring, Watching
                repository:   read Commit statuses, Contents, Issues, Metadata, Pull Requests
  USER_NAME     the GitHub login to report on
"""
import datetime
import hashlib
import os
import time

import requests
from dateutil import relativedelta
from lxml import etree

HEADERS = {'authorization': 'token ' + os.environ['ACCESS_TOKEN']}
USER_NAME = os.environ['USER_NAME']
QUERY_COUNT = {'user_getter': 0, 'follower_getter': 0, 'pr_issue_getter': 0,
               'graph_repos_stars': 0, 'recursive_loc': 0, 'loc_query': 0}

# Width reserved for each value in the SVG, matching the layout the cards were generated
# with. A row renders as 5 + len(key) + reserve columns regardless of the value, which is
# what stops the right edge moving as the numbers grow. Below 3 spare columns
# justify_format() collapses the leader dots and the row shrinks.
#
# These must equal tools/gen_svg.py's RESERVES. Regenerate the cards and run
# `python tools/gen_svg.py --reserves` to reprint them; test_today.py fails if they drift.
RESERVE = {'age_data': 55, 'repo_data': 56, 'contrib_data': 50, 'org_data': 48,
           'star_data': 56, 'follower_data': 52, 'commit_data': 54, 'pr_data': 48,
           'issue_data': 55, 'loc_data': 38, 'loc_add': 50, 'loc_del': 48}

CACHE_DIR = 'cache'
COMMENT_SIZE = 7  # header lines in the cache file, skipped when parsing


def daily_readme(start):
    """'XX years, XX months, XX days' since start."""
    diff = relativedelta.relativedelta(datetime.datetime.today(), start)
    return '{} {}, {} {}, {} {}'.format(
        diff.years, 'year' + format_plural(diff.years),
        diff.months, 'month' + format_plural(diff.months),
        diff.days, 'day' + format_plural(diff.days))


def format_plural(unit):
    return 's' if unit != 1 else ''


def simple_request(func_name, query, variables):
    request = requests.post('https://api.github.com/graphql',
                            json={'query': query, 'variables': variables}, headers=HEADERS)
    if request.status_code == 200:
        return request
    raise Exception(func_name, ' has failed with a', request.status_code, request.text, QUERY_COUNT)


def graph_repos_stars(count_type, owner_affiliation, cursor=None):
    """Total repository or star count."""
    query_count('graph_repos_stars')
    query = '''
    query ($owner_affiliation: [RepositoryAffiliation], $login: String!, $cursor: String) {
        user(login: $login) {
            repositories(first: 100, after: $cursor, ownerAffiliations: $owner_affiliation) {
                totalCount
                edges { node { ... on Repository { nameWithOwner stargazers { totalCount } } } }
                pageInfo { endCursor hasNextPage }
            }
        }
    }'''
    variables = {'owner_affiliation': owner_affiliation, 'login': USER_NAME, 'cursor': cursor}
    request = simple_request(graph_repos_stars.__name__, query, variables)
    if count_type == 'repos':
        return request.json()['data']['user']['repositories']['totalCount']
    elif count_type == 'stars':
        return stars_counter(request.json()['data']['user']['repositories']['edges'])


def recursive_loc(owner, repo_name, data, cache_comment,
                  addition_total=0, deletion_total=0, my_commits=0, cursor=None):
    """Fetch USER_NAME's commits 100 at a time and tally their lines.

    The author filter is applied server-side. Upstream fetches every commit in the repo and
    discards other people's client-side, which is unusable at this account's scale: it is a
    member of frappe and holds forks of erpnext/frappe, so the walk covers ~320k commits
    (~3,200 requests, hours, and the anti-abuse limit long before the end). Nearly all of
    those commits belong to other people -- the erpnext fork alone is 57k commits, none of
    them this user's. Filtering by author turns that repo into a single empty page.
    """
    query_count('recursive_loc')
    query = '''
    query ($repo_name: String!, $owner: String!, $cursor: String, $author_id: ID!) {
        repository(name: $repo_name, owner: $owner) {
            defaultBranchRef { target { ... on Commit {
                history(first: 100, after: $cursor, author: {id: $author_id}) {
                    totalCount
                    edges { node { ... on Commit { committedDate }
                            author { user { id } } deletions additions } }
                    pageInfo { endCursor hasNextPage }
                }
            } } }
        }
    }'''
    variables = {'repo_name': repo_name, 'owner': owner, 'cursor': cursor,
                 'author_id': OWNER_ID['id']}
    # Not simple_request(): the cache has to be flushed to disk before raising.
    request = requests.post('https://api.github.com/graphql',
                            json={'query': query, 'variables': variables}, headers=HEADERS)
    if request.status_code == 200:
        if request.json()['data']['repository']['defaultBranchRef'] is not None:
            return loc_counter_one_repo(
                owner, repo_name, data, cache_comment,
                request.json()['data']['repository']['defaultBranchRef']['target']['history'],
                addition_total, deletion_total, my_commits)
        return 0
    force_close_file(data, cache_comment)
    if request.status_code == 403:
        raise Exception('Too many requests in a short amount of time!\n'
                        'You\'ve hit the non-documented anti-abuse limit!')
    raise Exception('recursive_loc() has failed with a', request.status_code, request.text, QUERY_COUNT)


def loc_counter_one_repo(owner, repo_name, data, cache_comment, history,
                         addition_total, deletion_total, my_commits):
    for node in history['edges']:
        if node['node']['author']['user'] == OWNER_ID:
            my_commits += 1
            addition_total += node['node']['additions']
            deletion_total += node['node']['deletions']
    if history['edges'] == [] or not history['pageInfo']['hasNextPage']:
        return addition_total, deletion_total, my_commits
    return recursive_loc(owner, repo_name, data, cache_comment,
                         addition_total, deletion_total, my_commits, history['pageInfo']['endCursor'])


def loc_query(owner_affiliation, comment_size=0, force_cache=False, cursor=None, edges=None):
    """Walk every accessible repository, 60 at a time.

    60 is deliberate: larger pages time out with a 502, smaller ones make enough requests
    to trip the abuse limit and 502 anyway.
    """
    edges = [] if edges is None else edges
    query_count('loc_query')
    query = '''
    query ($owner_affiliation: [RepositoryAffiliation], $login: String!, $cursor: String) {
        user(login: $login) {
            repositories(first: 60, after: $cursor, ownerAffiliations: $owner_affiliation) {
                edges { node { ... on Repository {
                    nameWithOwner
                    defaultBranchRef { target { ... on Commit { history { totalCount } } } }
                } } }
                pageInfo { endCursor hasNextPage }
            }
        }
    }'''
    variables = {'owner_affiliation': owner_affiliation, 'login': USER_NAME, 'cursor': cursor}
    request = simple_request(loc_query.__name__, query, variables)
    page = request.json()['data']['user']['repositories']
    if page['pageInfo']['hasNextPage']:
        edges += page['edges']
        return loc_query(owner_affiliation, comment_size, force_cache, page['pageInfo']['endCursor'], edges)
    return cache_builder(edges + page['edges'], comment_size, force_cache)


def cache_filename():
    return os.path.join(CACHE_DIR, hashlib.sha256(USER_NAME.encode('utf-8')).hexdigest() + '.txt')


def cache_builder(edges, comment_size, force_cache, loc_add=0, loc_del=0):
    """Recount lines only for repositories whose commit count changed since last run."""
    cached = True
    filename = cache_filename()
    os.makedirs(CACHE_DIR, exist_ok=True)
    try:
        with open(filename, 'r') as f:
            data = f.readlines()
    except FileNotFoundError:
        data = ['This line is a comment block. Write whatever you want here.\n'] * comment_size
        with open(filename, 'w') as f:
            f.writelines(data)

    if len(data) - comment_size != len(edges) or force_cache:
        cached = False
        flush_cache(edges, filename, comment_size)
        with open(filename, 'r') as f:
            data = f.readlines()

    cache_comment = data[:comment_size]
    data = data[comment_size:]
    for index in range(len(edges)):
        repo_hash, commit_count, *__ = data[index].split()
        if repo_hash == hashlib.sha256(edges[index]['node']['nameWithOwner'].encode('utf-8')).hexdigest():
            try:
                if int(commit_count) != edges[index]['node']['defaultBranchRef']['target']['history']['totalCount']:
                    owner, repo_name = edges[index]['node']['nameWithOwner'].split('/')
                    loc = recursive_loc(owner, repo_name, data, cache_comment)
                    data[index] = (repo_hash + ' '
                                   + str(edges[index]['node']['defaultBranchRef']['target']['history']['totalCount'])
                                   + ' ' + str(loc[2]) + ' ' + str(loc[0]) + ' ' + str(loc[1]) + '\n')
            except TypeError:  # empty repository
                data[index] = repo_hash + ' 0 0 0 0\n'
    with open(filename, 'w') as f:
        f.writelines(cache_comment)
        f.writelines(data)
    for line in data:
        loc = line.split()
        loc_add += int(loc[3])
        loc_del += int(loc[4])
    return [loc_add, loc_del, loc_add - loc_del, cached]


def flush_cache(edges, filename, comment_size):
    """Wipe the cache, keeping the comment block. Runs when the repo count changes."""
    with open(filename, 'r') as f:
        data = f.readlines()[:comment_size] if comment_size > 0 else []
    with open(filename, 'w') as f:
        f.writelines(data)
        for node in edges:
            f.write(hashlib.sha256(node['node']['nameWithOwner'].encode('utf-8')).hexdigest() + ' 0 0 0 0\n')


def force_close_file(data, cache_comment):
    """Salvage partial cache data when a query blows up mid-walk."""
    filename = cache_filename()
    with open(filename, 'w') as f:
        f.writelines(cache_comment)
        f.writelines(data)
    print('There was an error while writing to the cache file. The file,', filename,
          'has had the partial data saved and closed.')


def stars_counter(data):
    return sum(node['node']['stargazers']['totalCount'] for node in data)


def svg_overwrite(filename, stats):
    """Write the freshly calculated values into the SVG.

    Takes a {element_id: value} dict rather than positional arguments, and drives the write
    off RESERVE so a row cannot be laid out and then silently not written. Upstream takes
    seven positional args and forgets to write one of them (age_data), which is why its
    Uptime row is frozen at whatever was last committed by hand.
    """
    missing = set(stats) - set(RESERVE)
    assert not missing, f'no reserve defined for {missing}'
    tree = etree.parse(filename)
    root = tree.getroot()
    for element_id, value in stats.items():
        justify_format(root, element_id, value, RESERVE[element_id])
    tree.write(filename, encoding='utf-8', xml_declaration=True)


def justify_format(root, element_id, new_text, length=0):
    """Set the element's text and pad the preceding dots so the value stays right-aligned."""
    if isinstance(new_text, int):
        new_text = f"{'{:,}'.format(new_text)}"
    new_text = str(new_text)
    find_and_replace(root, element_id, new_text)
    just_len = max(0, length - len(new_text))
    if just_len <= 2:
        dot_string = {0: '', 1: ' ', 2: '. '}[just_len]
    else:
        dot_string = ' ' + ('.' * just_len) + ' '
    find_and_replace(root, f'{element_id}_dots', dot_string)


def find_and_replace(root, element_id, new_text):
    element = root.find(f".//*[@id='{element_id}']")
    if element is not None:
        element.text = new_text


def commit_counter(comment_size):
    """Total commits, read back out of the cache cache_builder just wrote."""
    with open(cache_filename(), 'r') as f:
        data = f.readlines()
    return sum(int(line.split()[2]) for line in data[comment_size:])


def user_getter(username):
    """Account id, creation date and org memberships -- all three in one request."""
    query_count('user_getter')
    query = '''
    query($login: String!){
        user(login: $login) {
            id
            createdAt
            organizations(first: 10) { nodes { login } }
        }
    }'''
    request = simple_request(user_getter.__name__, query, {'login': username})
    user = request.json()['data']['user']
    orgs = ', '.join(node['login'] for node in user['organizations']['nodes'])
    return {'id': user['id']}, user['createdAt'], orgs


def follower_getter(username):
    query_count('follower_getter')
    query = '''
    query($login: String!){
        user(login: $login) { followers { totalCount } }
    }'''
    request = simple_request(follower_getter.__name__, query, {'login': username})
    return int(request.json()['data']['user']['followers']['totalCount'])


def pr_issue_getter(username):
    """Pull requests and issues opened by the user, in one request."""
    query_count('pr_issue_getter')
    query = '''
    query($login: String!){
        user(login: $login) {
            pullRequests { totalCount }
            issues { totalCount }
        }
    }'''
    request = simple_request(pr_issue_getter.__name__, query, {'login': username})
    user = request.json()['data']['user']
    return int(user['pullRequests']['totalCount']), int(user['issues']['totalCount'])


def query_count(funct_id):
    global QUERY_COUNT
    QUERY_COUNT[funct_id] += 1


def perf_counter(funct, *args):
    start = time.perf_counter()
    funct_return = funct(*args)
    return funct_return, time.perf_counter() - start


def formatter(query_type, difference, funct_return=False, whitespace=0):
    print('{:<23}'.format('   ' + query_type + ':'), sep='', end='')
    print('{:>12}'.format('%.4f' % difference + ' s ')) if difference > 1 else print(
        '{:>12}'.format('%.4f' % (difference * 1000) + ' ms'))
    if whitespace:
        return f"{'{:,}'.format(funct_return): <{whitespace}}"
    return funct_return


if __name__ == '__main__':
    print('Calculation times:')
    user_data, user_time = perf_counter(user_getter, USER_NAME)
    OWNER_ID, acc_date, org_data = user_data
    formatter('account data', user_time)

    # Uptime runs from the account's creation rather than a birthday.
    account_born = datetime.datetime.strptime(acc_date, '%Y-%m-%dT%H:%M:%SZ')
    age_data, age_time = perf_counter(daily_readme, account_born)
    formatter('age calculation', age_time)

    total_loc, loc_time = perf_counter(loc_query, ['OWNER', 'COLLABORATOR', 'ORGANIZATION_MEMBER'], COMMENT_SIZE)
    formatter('LOC (cached)', loc_time) if total_loc[-1] else formatter('LOC (no cache)', loc_time)
    commit_data, commit_time = perf_counter(commit_counter, COMMENT_SIZE)
    star_data, star_time = perf_counter(graph_repos_stars, 'stars', ['OWNER'])
    repo_data, repo_time = perf_counter(graph_repos_stars, 'repos', ['OWNER'])
    contrib_data, contrib_time = perf_counter(graph_repos_stars, 'repos',
                                              ['OWNER', 'COLLABORATOR', 'ORGANIZATION_MEMBER'])
    follower_data, follower_time = perf_counter(follower_getter, USER_NAME)
    pr_issue, pr_time = perf_counter(pr_issue_getter, USER_NAME)
    pr_data, issue_data = pr_issue

    for index in range(len(total_loc) - 1):
        total_loc[index] = '{:,}'.format(total_loc[index])

    stats = {
        'age_data': age_data,
        'repo_data': repo_data,
        'contrib_data': contrib_data,
        'org_data': org_data,
        'star_data': star_data,
        'follower_data': follower_data,
        'commit_data': commit_data,
        'pr_data': pr_data,
        'issue_data': issue_data,
        'loc_data': total_loc[2],
        'loc_add': total_loc[0],
        'loc_del': total_loc[1],
    }
    svg_overwrite('dark_mode.svg', stats)
    svg_overwrite('light_mode.svg', stats)

    print('\033[F\033[F\033[F\033[F\033[F\033[F\033[F\033[F',
          '{:<21}'.format('Total function time:'),
          '{:>11}'.format('%.4f' % (user_time + age_time + loc_time + commit_time
                                    + star_time + repo_time + contrib_time + pr_time)),
          ' s \033[E\033[E\033[E\033[E\033[E\033[E\033[E\033[E', sep='')
    print('Total GitHub GraphQL API calls:', '{:>3}'.format(sum(QUERY_COUNT.values())))
    for funct_name, count in QUERY_COUNT.items():
        print('{:<28}'.format('   ' + funct_name + ':'), '{:>6}'.format(count))
