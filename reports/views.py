from django.shortcuts import render
import requests
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup
from groq import Groq
import markdown

# Initialize the Groq client with a placeholder for the API key
# Replace 'your-groq-api-key' with the actual API key or use another method to securely manage it
GROQ_API_KEY = "your-groq-api-key"
client = Groq(api_key=GROQ_API_KEY)

def get_player_url(player_name):
    search_name = player_name.replace(" ", "-")
    search_url = f"https://fbref.com/search/search.fcgi?search={search_name}"
    
    try:
        response = requests.get(search_url)
        response.raise_for_status()  # Raise an exception for HTTP errors
        soup = BeautifulSoup(response.text, 'html.parser')
        first_result = soup.find('a', href=True)
        
        if first_result:
            player_url = first_result['href']
            player_uid = player_url.split('/')[5]
            url = f'https://fbref.com/en/players/{player_uid}/{player_name.replace(" ", "-")}'
            return url
        else:
            return None
    except requests.RequestException as e:
        print(f"Error fetching player URL: {e}")
        return None

def get_player_report(request):
    if request.method == 'POST':
        player_name = request.POST.get('player_name')
        url = get_player_url(player_name)
        attrs = 'scout_summary_AM'

        if url:
            try:
                df = pd.read_html(url, attrs={'id': attrs})[0]
                response = requests.get(url)
                response.raise_for_status()  # Raise an exception for HTTP errors
                soup = BeautifulSoup(response.text, 'html.parser')

                position = soup.select_one('p:-soup-contains("Position")').text.split(':')[-2].split(' ')[0].strip()
                birthday = soup.select_one('span[id="necro-birth"]').text.strip()
                age = (datetime.now() - datetime.strptime(birthday, '%B %d, %Y')).days // 365
                team = soup.select_one('p:-soup-contains("Club")').text.split(':')[-1].strip()

                prompt = f"""
                I need you to create a scouting report on {player_name}. Can you provide me with a summary of their strengths and weaknesses?

                Here is the data I have on him:

                Player: {player_name}
                Position: {position}
                Age: {age}
                Team: {team}

                {df.to_markdown()}

                Return the scouting report in the following markdown format:

                # Scouting Report for {player_name}

                ## Strengths
                < a list of 1 to 3 strengths >

                ## Weaknesses
                < a list of 1 to 3 weaknesses >

                ## Summary
                < a brief summary of the player's overall performance and if he would be beneficial to the team >
                """

                try:
                    response = client.chat.completions.create(
                        messages=[
                            {"role": "user", "content": prompt}
                        ],
                        model="llama3-8b-8192",  # Adjust model name as needed
                    )
                    scouting_report = response.choices[0].message.content
                    html_report = markdown.markdown(scouting_report)

                # Render the report in a separate template
                    return render(request, 'report.html', {'report': html_report, 'player_name': player_name})

                except Exception as e:
                    return render(request, 'index.html', {'error': f"Error with Groq API: {e}"})

            except Exception as e:
                return render(request, 'index.html', {'error': f"Error fetching player data: {e}"})

    # Render the index page if not POST request
    return render(request, 'index.html')
