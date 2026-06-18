import core.wx as wx 
import core.db as db
from core.config import DEBUG,cfg
from core.models.article import Article
from datetime import datetime

DB=db.Db(tag="文章采集API")

def UpdateArticle(art:dict,check_exist=True):
    mps_count=0

    # Convert timestamp to datetime if 'updated_at' exists in art
    if 'updated_at' in art:
        try:
            art['updated_at'] = datetime.fromtimestamp(int(art['updated_at']))
        except (ValueError, OverflowError) as e:
            print(f"Error converting 'updated_at': {e}")
            return False

    if DEBUG:
        # DB.delete_article(art)
        pass
    if  DB.add_article(art,check_exist=check_exist):
        mps_count=mps_count+1
        return True
    return False
def Update_Over(data=None):
    print("更新完成")
    pass