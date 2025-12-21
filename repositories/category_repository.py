"""Category Repository - Data access layer for categories."""
from repositories.base_repository import BaseRepository


class CategoryRepository(BaseRepository):
    """Repository for category database operations."""
    
    def __init__(self):
        """Initialize category repository."""
        super().__init__('categories')
    
    def get_all(self, include_deleted=False):
        """Get all categories."""
        if include_deleted:
            query = "SELECT * FROM categories"
        else:
            query = "SELECT * FROM categories WHERE is_deleted = 0"
        return self.execute_query(query)
    
    def get_by_id(self, category_id):
        """Get category by ID."""
        query = "SELECT * FROM categories WHERE id = ?"
        return self.execute_query_one(query, [category_id])
    
    def get_by_name(self, name):
        """Get category by name."""
        query = "SELECT * FROM categories WHERE category_name = ? AND is_deleted = 0"
        return self.execute_query_one(query, [name])
    
    def create(self, name):
        """Create new category."""
        query = "INSERT INTO categories (category_name) VALUES (?)"
        return self.create(query, [name])
    
    def update(self, category_id, name):
        """Update category."""
        query = "UPDATE categories SET category_name = ? WHERE id = ?"
        return self.update(query, [name, category_id])
    
    def delete(self, category_id, soft_delete=True):
        """Delete category."""
        if soft_delete:
            query = "UPDATE categories SET is_deleted = 1 WHERE id = ?"
            return self.update(query, [category_id])
        else:
            query = "DELETE FROM categories WHERE id = ?"
            return self.delete(query, [category_id])
