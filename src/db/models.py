from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text, BigInteger
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()

class Wallet(Base):
    __tablename__ = 'wallets'
    
    id = Column(Integer, primary_key=True)
    address = Column(String, unique=True, index=True)
    name = Column(String)
    chain = Column(String) # 'EVM', 'SOL'
    is_active = Column(Boolean, default=True)
    confidence_score = Column(Integer) # From HTML
    twitter_handle = Column(String, nullable=True) # @handle
    
    # Reputation System (Enhancement #1)
    # A = Verified profitable, B = Mixed/unclear, C = Known scammer, U = Unrated
    reputation_tier = Column(String, default="U")
    reputation_notes = Column(Text, nullable=True)  # Why this rating
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    transactions = relationship("Transaction", back_populates="wallet")
    moments = relationship("Moment", back_populates="wallet")
    stats = relationship("WalletStats", back_populates="wallet", uselist=False)

class WalletStats(Base):
    __tablename__ = 'wallet_stats'
    
    id = Column(Integer, primary_key=True)
    wallet_id = Column(Integer, ForeignKey('wallets.id'), unique=True)
    
    # Profile Metrics
    avg_buy_sol = Column(Float, default=0.0)
    max_buy_sol = Column(Float, default=0.0)
    total_tx_count = Column(Integer, default=0)
    win_rate = Column(Float, nullable=True)
    
    # Strategy Fingerprint (Phase 3)
    avg_hold_time_hours = Column(Float, nullable=True)
    preferred_sector = Column(String, nullable=True)  # MEME, DEFI, NFT, etc.
    exit_pattern = Column(String, nullable=True)  # DUMP, LADDER, HOLD
    trades_analyzed = Column(Integer, default=0)
    
    # Alpha Decay (Phase 4)
    alpha_score = Column(Float, default=100.0)  # 0-100, decays with copiers
    avg_copiers_per_trade = Column(Float, default=0.0)
    
    # Predictive Engine (Phase 1)
    reload_buy_probability = Column(Float, nullable=True)  # % chance of buy after reload
    avg_time_to_buy_after_reload = Column(Integer, nullable=True)  # minutes
    
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    wallet = relationship("Wallet", back_populates="stats")

class Transaction(Base):
    __tablename__ = 'transactions'

    id = Column(Integer, primary_key=True)
    wallet_id = Column(Integer, ForeignKey('wallets.id'))
    tx_hash = Column(String, unique=True, index=True)
    chain = Column(String)
    block_number = Column(BigInteger)
    timestamp = Column(DateTime(timezone=True))
    
    # Simple details
    token_symbol = Column(String, nullable=True)
    token_address = Column(String, nullable=True)
    amount = Column(Float, nullable=True)
    amount_usd = Column(Float, nullable=True)
    tx_type = Column(String) # 'SWAP', 'TRANSFER', 'APPROVAL'
    
    wallet = relationship("Wallet", back_populates="transactions")

class Moment(Base):
    __tablename__ = 'moments'
    
    id = Column(Integer, primary_key=True)
    wallet_id = Column(Integer, ForeignKey('wallets.id'))
    tx_hash = Column(String, ForeignKey('transactions.tx_hash'))
    
    moment_type = Column(String) # 'BIG_BUY', 'NEW_TOKEN', 'DUMP'
    description = Column(Text)
    severity = Column(Integer) # 1-10
    
    detected_at = Column(DateTime(timezone=True), server_default=func.now())
    
    wallet = relationship("Wallet", back_populates="moments")
    transaction = relationship("Transaction")

class User(Base):
    __tablename__ = "users"

    chat_id = Column(BigInteger, primary_key=True, index=True)
    username = Column(String, nullable=True)
    access_level = Column(String, default="RESEARCHER") # FREE, COPY_TRADER, RESEARCHER
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Relation(Base):
    __tablename__ = 'relations'
    
    id = Column(Integer, primary_key=True)
    wallet_a_id = Column(Integer, ForeignKey('wallets.id'))
    wallet_b_id = Column(Integer, ForeignKey('wallets.id'))
    
    relation_type = Column(String) # 'CO_INVESTMENT', 'SAME_TOKEN_SAME_TIME'
    token_address = Column(String, nullable=True)
    confidence = Column(Float)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ReloadEvent(Base):
    """Tracks incoming funds to predict upcoming buys."""
    __tablename__ = 'reload_events'
    
    id = Column(Integer, primary_key=True)
    wallet_id = Column(Integer, ForeignKey('wallets.id'), index=True)
    tx_hash = Column(String, unique=True)
    
    amount = Column(Float)  # Amount received (SOL/ETH)
    source_address = Column(String, nullable=True)  # Who sent it
    
    # Prediction tracking
    followed_by_buy = Column(Boolean, nullable=True)  # Did a buy happen after?
    time_to_buy_minutes = Column(Integer, nullable=True)  # How long until the buy?
    buy_tx_hash = Column(String, nullable=True)  # Link to the buy tx
    
    detected_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)  # When we determined outcome
    
    wallet = relationship("Wallet")

class FundingLink(Base):
    """Tracks wallet-to-wallet funding for cabal detection."""
    __tablename__ = 'funding_links'
    
    id = Column(Integer, primary_key=True)
    source_address = Column(String, index=True)  # Who sent funds
    dest_wallet_id = Column(Integer, ForeignKey('wallets.id'), index=True)
    
    amount = Column(Float)
    tx_hash = Column(String)
    
    detected_at = Column(DateTime(timezone=True), server_default=func.now())
    
    dest_wallet = relationship("Wallet")

