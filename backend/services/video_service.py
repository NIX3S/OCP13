import os
from fastapi import FastAPI, HTTPException
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()  # Charge les variables du .env

YOUTUBE_API_KEY = os.getenv("YTB_KEY")
if not YOUTUBE_API_KEY:
    raise ValueError("La clé YouTube (YTB_KEY) doit être définie dans .env")

youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

app = FastAPI()

@app.get("/api/v1/videos/{opening}")
def get_videos(opening: str, max_results: int = 5):
    """
    Recherche des vidéos YouTube pédagogiques pour l'ouverture donnée.
    """
    try:
        query = f"{opening} chess opening tutorial explanation"
        request = youtube.search().list(
            q=query,
            part="snippet",
            type="video",
            maxResults=max_results,
            order="relevance"
        )
        response = request.execute()
        
        videos = []
        for item in response.get("items", []):
            video_id = item["id"]["videoId"]
            videos.append({
                "title": item["snippet"]["title"],
                "description": item["snippet"]["description"],
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "channel": item["snippet"]["channelTitle"],
                "published_at": item["snippet"]["publishedAt"]
            })
        
        if not videos:
            return {"opening": opening, "videos": [], "message": "Aucune vidéo trouvée"}
        
        return {"opening": opening, "videos": videos}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))