# -*- coding: utf-8 -*-
"""
Created on Fri Dec 21 15:17:39 2018

@author: Sony
"""


import datetime
import pandas as pd
import time
import re

#my_connections = pd.read_csv('LinkedInData/Connections.csv')
#print(pd.isnull(my_connections.iloc[0]['Email Address']))

# Read in the positions I've had so far. Used to calculate my experience in years.
my_positions = pd.read_csv('LinkedInData/Positions.csv')
my_experience = 0

# If I've been employed before, then...
if len(my_positions) > 0:
    # Get the start date of my first job.
    career_start_str = my_positions.iloc[0]['Started On']
    
    # And the end date of my latest job.
    career_end_str = my_positions.iloc[len(my_positions) - 1]['Finished On']
    
    # A bit redundant, this check. But might as well...
    if pd.isnull(career_start_str):
        my_experience = 0
    else:
        # Extract the year of leaving the latest job.
        career_start_year = int(career_start_str[-4:])
        if pd.isnull(career_end_str) or career_end_str == 'Present':
            # If I'm still working
            career_end_year = int(datetime.datetime.now().year)
        else:
            # If not
            career_end_year = int(career_end_str[-4:])
            
        # And calculate the experience
        my_experience = career_end_year - career_start_year
        

# Read in my skills.
my_skills = pd.read_csv('LinkedInData/Skills.csv')
my_skills['Name'] = my_skills['Name'].str.lower()
#print(len(my_skills))

# Read in the Amazon jobs data.
amazon_jobs = pd.read_csv('amazon-job-skills/amazon_jobs_dataset.csv')
amazon_jobs = amazon_jobs.loc[:, ~amazon_jobs.columns.str.contains('^Unnamed')]
#print(amazon_jobs.columns)

def split_location(location):
    '''
    Splits a location into country, state, and city.
    '''
    pieces = location.split(', ')
    
    cntry = pieces[0].strip() if len(pieces) > 0 else 'NA'
    state = pieces[1].strip() if len(pieces) > 1 else 'NA'
    city  = pieces[2].strip() if len(pieces) > 2 else 'NA'
    
    return cntry, state, city

matching_skills = []
exp_list = []
country_list = []
state_list = []
city_list = []

# For each job posting...
for ind, row in amazon_jobs.iterrows():
    # Get the job location
    location = row['location']
    
    # Split it
    cntry, state, city = split_location(location)
    
    # And store the data to put the values back as individual columns.
    country_list.append(cntry)
    state_list.append(state)
    city_list.append(city)
    
    # Read in the basic and preferred qualifications.
    basic = row['BASIC QUALIFICATIONS']
    pref  = row['PREFERRED QUALIFICATIONS']
    
    if pd.isnull(basic) and pd.isnull(pref):
        # If no qualification details are available, assume I can apply for it.
        exp_list.append(0)
        matching_skills.append(100.0)
        continue
    
    # Find the years of experience in the qualifications text via regex
    exp_match = []
    if not pd.isnull(basic):
        basic.replace('\n', ' ')
        basic = basic.lower()
        exp_match = re.findall(r'(\d+)\+? years?', basic)
    
    if not pd.isnull(pref):
        pref.replace('\n', ' ')
        pref = pref.lower()
        exp_match += re.findall(r'(\d+)\+? years?', pref)
    
    # Convert to int.
    exp_match = [int(x) for x in exp_match]
    
    # Get the required experience for the job. If it's greater than my current
    # experience, then ignore it.
    required_experience = min(exp_match) if len(exp_match) > 0 else 0
    exp_list.append(required_experience)
    
    # Check if either the basic or preferred qualifications contains any of my skills.
    basics = 0
    prefers = 0
    for s in my_skills['Name']:
        if s in basic:
            basics += 1
            
        if s in pref:
            prefers += 1
    
    # Arbitrary formula.
    match_percent = ((basics + prefers))/(2 * len(my_skills)) * 100
    matching_skills.append(match_percent)
    
# Add in columns to Amazon jobs.
amazon_jobs['Required Experience'] = exp_list
amazon_jobs['Skill Match Percent'] = matching_skills
amazon_jobs['Country'] = country_list
amazon_jobs['State'] = state_list
amazon_jobs['City'] = city_list

# And drop the location column
amazon_jobs.drop(['location'], axis=1, inplace=True)

# Now get my preferences and extract the locations that I want to work at.
my_job_preferences = pd.read_csv('LinkedInData/Jobs/Job Seeker Preferences.csv')
preferred_locations = my_job_preferences['Locations'][0]
print(preferred_locations)

loc_list = preferred_locations.split('[')[1:]
loc_list = [x.split(']')[0] for x in loc_list]
preferred_locations = pd.DataFrame(loc_list, columns=['location'])

# Dataset containing the codes for countries. Used for data normalization.
ccodes = pd.read_csv('countries-iso-codes/wikipedia-iso-country-codes.csv')

# Pretty much the same algorithm as before. Extract country, city, and state from the preference data.
country_list = []
state_list = []
city_list = []
for ind, row in preferred_locations.iterrows():
    location = row['location']
    
    # ONE CAVEAT: The location data is stored in LinkedIn as [City, State, Country] as opposed to [Country, State, City] in the Amazon jobs dataset. Again, normalization.
    city, state, cntry = split_location(location)
    print(ccodes[ccodes['English short name lower case'] == cntry]['Alpha-2 code'].values[0])
    country_list.append(ccodes[ccodes['English short name lower case'] == cntry]['Alpha-2 code'].values[0])
    state_list.append(state)
    city_list.append(city)

preferred_locations['Country'] = country_list
preferred_locations['State'] = state_list
preferred_locations['City'] = city_list
preferred_locations.drop(['location'], axis=1, inplace=True)

# Finally, get the jobs that I can apply to.
# The following rules apply:
# 1. Experience required can be >= 0.75 * my_exp and <= my_exp
# 2. Experience required is allowed to be >= my_exp and <= 1.75 * my_exp, as long as the skills match at least 35% (arbitrary)
# 3. The job must be in the same countries as my preferences.
can_apply = amazon_jobs[(((amazon_jobs['Required Experience'] >= my_experience * .75) & (amazon_jobs['Required Experience'] <= my_experience)) | (((amazon_jobs['Required Experience'] > my_experience) & (amazon_jobs['Required Experience'] <= my_experience * 1.75)) & (amazon_jobs['Skill Match Percent'] >= 35))) & (amazon_jobs['Country'].isin(preferred_locations['Country']))]

# Reset the index.
can_apply = can_apply.reset_index()



# ****************************************************************************
# Searching LinkedIn for jobs by location is problematic via Selenium.

from selenium import webdriver

my_job_applications = pd.read_csv('LinkedInData/Jobs/Job Applications.csv')
my_saved_jobs = pd.read_csv('LinkedInData/Jobs/Saved Jobs.csv')

url_list = []
interested_job_titles = list(set(my_job_applications['Job Title']))
interested_companies  = list(set(my_job_applications['Company Name']))
url_list += list(my_job_applications['Job Url'])
url_list += list(my_saved_jobs['Job Url'])

option = webdriver.ChromeOptions()
option.add_argument("--incognito")    
driver_path = 'D:\chromedriver.exe'

for url in url_list:
    browser = webdriver.Chrome(driver_path)
    browser.get(url)
            
    time.sleep(5)
    browser.close()
    break

print(interested_job_titles)
print(interested_companies)

print(loc_list)

# loc_list now contains all of the locations that I'm interested in.
# I also have the job titles and job locations that I'm interested in.
# Now I need to make a call via the LinkedIn API searching for jobs.

# ****************************************************************************

'''
This method is no good for me. The API is very, VERY limited.
'''

from linkedin import linkedin

APPLICATON_KEY    = '81eyfqgj9v5n1b'
APPLICATON_SECRET = 'F9gW91n1i463fd9M'

RETURN_URL = 'https://localhost:8000'

permissions = ['r_basicprofile', 'r_emailaddress', 'w_share', 'rw_company_admin']

authentication = linkedin.LinkedInAuthentication(
                    APPLICATON_KEY,
                    APPLICATON_SECRET,
                    RETURN_URL,
                    permissions
                )

# open this url on your browser
print (authentication.authorization_url)

authentication.authorization_code = 'AQQ-0e-i12eTTN2eElhM0RyyJWAcYivGVwqOxRL073AePXpuj95D3COLMMT2JBE4UFUt7lahQTG3gkFFlGM-vbcDLfC1HL6Kq2ZLCFZau4i1_DAHX6s9vQ-1fKskZHY4JUeKjH2yiLzwVJsZedeb2ulEwoT_WUdJzC_Gx1MAq0FDiTzth5bijTn5vqK-4A'

result = authentication.get_access_token()

print ("Access Token:", result.access_token)
print ("Expires in (seconds):", result.expires_in)

token = result.access_token

application = linkedin.LinkedInApplication(token=token)

print(application.get_profile())
print(url_list)
print(application.get_job(job_id=283833840))

# ****************************************************************************

# For each location that I prefer...
for loc in loc_list:
    url_loc = loc.replace(' ', '%20')
    url_loc = url_loc.replace(',', '%2C')

    browser = webdriver.Chrome(driver_path)
    browser.get('https://www.linkedin.com/jobs/search/?location=' + url_loc)
    companies = browser.find_elements_by_xpath('//*[@itemtype="http://schema.org/ListItem"]')
    
    
    for c in companies:
        complete_url = c.find_element_by_tag_name('a').get_attribute('href')
        url_list.append(complete_url)
    time.sleep(5)
    browser.close()
    
    print(url_list)
    
    
    for link in url_list:
        browser = webdriver.Chrome(driver_path)
        browser.get(link)
        time.sleep(30)
        browser.close()
        break
    
    break

# ****************************************************************************

x = application.get_job(job_id=1021482444)
print(type(x))
print(x)


# IDEA: Instead of extracting skills from the job requirement, I could scan the job requirement for the list of skills I currently have. If around 60% of skills match, then I call the job as applicable. I scan around 100 (or as many as available) jobs per location.