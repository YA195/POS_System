"""Category model."""
from repositories.category_repository import CategoryRepository


class Category:
    """Model for managing product categories."""
    
    def __init__(self):
        """Initialize with repository."""
        self.repository = CategoryRepository()
    
    def get_all(self, include_deleted=False):
        """Get all categories from database."""
        return self.repository.get_all(include_deleted)
    
    def get_by_id(self, category_id):
        """Get category by ID."""
        return self.repository.get_by_id(category_id)
    
    def get_by_name(self, name):
        """Get category by name."""
        return self.repository.get_by_name(name)
    
    def create(self, data):
        """Create a new category."""
        return self.repository.create(data['category_name'])
    
    def update(self, category_id, data):
        """Update an existing category."""
        return self.repository.update(category_id, data['category_name'])
    
    def delete(self, category_id, soft_delete=True):
        """Delete a category (soft or hard delete)."""
        return self.repository.delete(category_id, soft_delete)
    
    def restore(self, category_id):
        """Restore a soft-deleted category."""
        conn = self.repository.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE categories SET is_deleted = 0 WHERE id = ?", [category_id])
        conn.commit()
        return cursor.rowcount
