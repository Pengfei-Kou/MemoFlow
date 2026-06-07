import sys
import os
import hashlib

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, select, delete
from app.database import engine
from app.models import Source, Block, Deck
from app.services.md_parser import parse_haodao_markdown

def fix_all():
    file_path = '/Users/pengfei/Projects/MemoFlow/郝炟英语口语.md'
    if not os.path.exists(file_path):
        print(f"File {file_path} not found.")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        text = f.read()
    
    parsed_sources = parse_haodao_markdown(text)
    
    with Session(engine) as session:
        # Save old block stats to restore reps/intervals if they match exactly
        old_blocks = session.exec(select(Block)).all()
        old_blocks_map = {}
        for ob in old_blocks:
            old_blocks_map[f"{ob.quiz}|||{ob.content}"] = ob
            
        print("Deleting old corrupted blocks...")
        session.exec(delete(Block))
        session.commit()
        
        deck = session.exec(select(Deck)).first()
        
        for section in parsed_sources:
            title = section['source_title']
            cards = section['cards']
            if not cards: continue
            
            src = session.exec(select(Source).where(Source.title == title)).first()
            if not src:
                content_hash = hashlib.md5(f"{deck.id}:{title}".encode()).hexdigest()
                source_text = "\n".join(f"{c['quiz']} / {c['content']}" for c in cards)
                src = Source(
                    title=title,
                    content_hash=content_hash,
                    original_text=source_text,
                    source_type="text",
                    deck_id=deck.id,
                )
                session.add(src)
                session.commit()
                session.refresh(src)
            else:
                src.original_text = "\n".join(f"{c['quiz']} / {c['content']}" for c in cards)
                session.add(src)
                
            seq = 1
            for c in cards:
                b = Block(
                    source_id=src.id,
                    sequence_number=seq,
                    content=c['content'],
                    quiz=c['quiz'],
                    notes=c.get('notes')
                )
                
                # Attempt to restore progress if exact match is found
                old_b = old_blocks_map.get(f"{b.quiz}|||{b.content}")
                if old_b and old_b.reps > 0:
                    b.reps = old_b.reps
                    b.interval = old_b.interval
                    b.ease_factor = old_b.ease_factor
                    b.first_reviewed_at = old_b.first_reviewed_at
                    b.last_review = old_b.last_review
                    b.next_review = old_b.next_review
                    b.is_suspended = old_b.is_suspended
                
                session.add(b)
                seq += 1
            
            session.commit()
            print(f"Restored source {title} with {len(cards)} cards")

if __name__ == '__main__':
    fix_all()
