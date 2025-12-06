"""Shift controller for business logic."""
from models.shift import Shift
from utils.logger import log_activity


class ShiftController:
    """Controller for shift-related business logic."""
    
    @staticmethod
    def start_shift(user_id, opening_balance=0):
        """Start a new shift."""
        # Check if there's already an active shift
        active_shift = Shift.get_active()
        if active_shift:
            raise ValueError("There is already an active shift. Please close it before starting a new one.")
        
        # Create new shift
        shift_id = Shift.create(user_id, opening_balance)
        
        # Log activity
        log_activity('START_SHIFT', f"Started shift with opening balance: {opening_balance}", 'shifts', shift_id)
        
        return shift_id
    
    @staticmethod
    def get_active_shift():
        """Get the currently active shift."""
        return Shift.get_active()
    
    @staticmethod
    def close_shift(shift_id, closing_data):
        """Close an active shift."""
        # Validate shift exists
        shift = Shift.get_by_id(shift_id)
        if not shift:
            raise ValueError(f"Shift {shift_id} not found")
        
        # Check if already closed
        if shift[3] is not None:  # Assuming column 3 is end_time
            raise ValueError("Shift is already closed")
        
        # Close shift
        Shift.close(shift_id, closing_data)
        
        # Log activity
        log_activity('CLOSE_SHIFT', f"Closed shift with closing balance: {closing_data.get('closing_balance', 0)}", 'shifts', shift_id)
        
        return True
    
    @staticmethod
    def get_shift_summary(shift_id):
        """Get comprehensive shift summary."""
        return Shift.get_summary(shift_id)
    
    @staticmethod
    def get_all_shifts():
        """Get all shifts."""
        return Shift.get_all()
