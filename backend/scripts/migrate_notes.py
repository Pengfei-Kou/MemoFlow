import sys
import os

# Add backend dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, select
from app.database import engine
from app.models import Source, Block
from app.services.md_parser import _parse_content_section

def migrate():
    with Session(engine) as session:
        sources = session.exec(select(Source)).all()
        print(f"Found {len(sources)} sources.")
        for src in sources:
            if not src.original_text:
                continue
            
            lines = src.original_text.splitlines()
            cards = _parse_content_section(lines)
            if not cards:
                continue
            
            old_blocks = session.exec(select(Block).where(Block.source_id == src.id).order_by(Block.sequence_number)).all()
            
            # Map old blocks by quiz+content
            old_blocks_map = {f"{b.quiz}|||{b.content}": b for b in old_blocks}
            
            # Delete old blocks
            for b in old_blocks:
                session.delete(b)
            
            session.commit()
            
            # Insert new blocks
            seq = 1
            for c in cards:
                key = f"{c['quiz']}|||{c['content']}"
                old_b = old_blocks_map.get(key)
                
                b = Block(
                    source_id=src.id,
                    sequence_number=seq,
                    content=c['content'],
                    quiz=c['quiz'],
                    notes=c.get('notes')
                )
                
                if old_b:
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
        print(f"Migrated source {src.id}: {src.title}")
    print("Done!")

if __name__ == "__main__":
    migrate()
