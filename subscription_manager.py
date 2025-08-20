from database_manager import db_manager
from datetime import datetime, timedelta

class SubscriptionManager:
    def __init__(self):
        pass
    
    def activate_subscription(self, user_id: int, subscription_type: str, days: int, activated_by: int):
        """فعال کردن اشتراک کاربر"""
        end_date = datetime.now() + timedelta(days=days)
        
        placeholder = "%s" if db_manager.is_postgres else "?"
        
        if db_manager.is_postgres:
            query = f"""
                INSERT INTO user_subscriptions (user_id, subscription_type, end_date, activated_by)
                VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder})
                ON CONFLICT (user_id) DO UPDATE SET
                    subscription_type = EXCLUDED.subscription_type,
                    end_date = EXCLUDED.end_date,
                    activated_by = EXCLUDED.activated_by,
                    is_active = TRUE,
                    start_date = CURRENT_TIMESTAMP
            """
        else:
            query = f"""
                INSERT OR REPLACE INTO user_subscriptions 
                (user_id, subscription_type, end_date, activated_by, is_active)
                VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, TRUE)
            """
        
        db_manager.execute(query, (user_id, subscription_type, end_date, activated_by))
        return True
    
    def check_subscription(self, user_id: int) -> bool:
        """بررسی وضعیت اشتراک کاربر"""
        placeholder = "%s" if db_manager.is_postgres else "?"
        
        query = f"""
            SELECT is_active, end_date FROM user_subscriptions 
            WHERE user_id = {placeholder} AND is_active = TRUE
        """
        
        result = db_manager.fetchone(query, (user_id,))
        
        if not result:
            return False
        
        end_date = datetime.fromisoformat(result['end_date'])
        if datetime.now() > end_date:
            # اشتراک منقضی شده
            self.deactivate_subscription(user_id)
            return False
        
        return True
    
    def deactivate_subscription(self, user_id: int):
        """غیرفعال کردن اشتراک"""
        placeholder = "%s" if db_manager.is_postgres else "?"
        query = f"UPDATE user_subscriptions SET is_active = FALSE WHERE user_id = {placeholder}"
        db_manager.execute(query, (user_id,))

subscription_manager = SubscriptionManager()
