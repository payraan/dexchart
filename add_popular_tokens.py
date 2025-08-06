from database_manager import db_manager
from datetime import datetime

# لیست توکن‌های محبوب Solana
popular_tokens = [
    ('JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN', 'JUP'),
    ('DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263', 'BONK'),
    ('EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v', 'USDC'),
    ('7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs', 'ETH'),
    ('HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3', 'PYTH'),
    ('AGFEad2et2ZJif9jaGpdMixQqvW5i81aBdvKe7PHNfz3', 'FTT'),
    ('hntyVP6YFm1Hg25TN9WGLqM12b8TQmcknKrdu1oxWux', 'HNT'),
    ('StepAscQoEioFxxWGnh2sLBDFp9d8rvKz2Yp39iDpyT', 'STEP'),
    ('RaydiumraydiumsAMbS2m7eBJkNqCRdJJRJTqCk9fg1', 'RAY'),
    ('SRMuApVNdxXokk5GT7XD5cUUgXMBCoAz2LHeuAoKWRt', 'SRM'),
    ('ATLASXmbPQxBUYbxPsV97usA3fPQYEqzQBUHgiFCUsXx', 'ATLAS'),
    ('iotEVVZLEywoTn1QdwNPddxPWszn3zFhEot3MfL9fns', 'IOT'),
]

now = datetime.now().isoformat()
added = 0

for address, symbol in popular_tokens:
    query = '''INSERT OR IGNORE INTO watchlist_tokens
              (address, symbol, pool_id, first_seen, last_active, status)
              VALUES (?, ?, ?, ?, ?, 'active')'''
    
    pool_id = f"solana_{address}"
    result = db_manager.execute(query, (address, symbol, pool_id, now, now))
    if result:
        added += 1
        print(f"✅ Added: {symbol}")

print(f"\n📊 Total new tokens added: {added}")

# چک تعداد کل
result = db_manager.fetchone('SELECT COUNT(*) as count FROM watchlist_tokens')
print(f"📊 Total tokens in watchlist: {result['count']}")
