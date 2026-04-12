"""
Execution Engine Test Script

Tests the complete execution flow in paper mode:
Signal → Safety Checks → Order → Position Management
"""

import asyncio
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from execution.broker_interface import BrokerConfig
from execution.zerodha_adapter import ZerodhaAdapter
from execution.order_manager import OrderManager, OrderConfig
from execution.position_manager import PositionManager
from execution.execution_engine import (
    ExecutionEngine,
    TradingSignal,
    SignalConfig,
    SafetyRules
)


async def test_execution_flow():
    """Test complete execution flow"""
    
    print("="*80)
    print("🧪 EXECUTION ENGINE TEST - PAPER MODE")
    print("="*80)
    print()
    
    # Step 1: Initialize Broker (Paper Mode)
    print("1️⃣ Initializing Zerodha broker (Paper Mode)...")
    broker_config = BrokerConfig(
        name="Zerodha",
        api_key="test_api_key",
        api_secret="test_api_secret",
        paper_mode=True  # ✅ Paper mode
    )
    
    broker = ZerodhaAdapter(broker_config)
    connected = await broker.connect()
    
    if not connected:
        print("❌ Failed to connect to broker")
        return
    
    print(f"✅ Broker connected (paper_mode={broker.is_paper_mode()})")
    print()
    
    # Step 2: Initialize Order Manager
    print("2️⃣ Initializing Order Manager...")
    order_config = OrderConfig(
        max_retries=3,
        retry_delay_seconds=1.0,
        timeout_seconds=30.0
    )
    order_manager = OrderManager(broker, order_config)
    print("✅ Order Manager ready")
    print()
    
    # Step 3: Initialize Position Manager
    print("3️⃣ Initializing Position Manager...")
    position_manager = PositionManager(broker, max_positions=5)
    await position_manager.sync_positions()
    print("✅ Position Manager ready")
    print(f"   Open positions: {position_manager.get_position_count()}")
    print()
    
    # Step 4: Initialize Execution Engine
    print("4️⃣ Initializing Execution Engine...")
    signal_config = SignalConfig(
        default_position_size=0.01,
        max_position_size=0.1,
        use_dynamic_sizing=False
    )
    
    safety_rules = SafetyRules(
        max_positions=5,
        max_trades_per_day=20,
        max_loss_per_day=1000.0,
        block_duplicate_signals=True,
        allow_hedging=False
    )
    
    execution_engine = ExecutionEngine(
        broker=broker,
        order_manager=order_manager,
        position_manager=position_manager,
        signal_config=signal_config,
        safety_rules=safety_rules
    )
    print("✅ Execution Engine ready")
    print()
    
    # Step 5: Test Signal Processing
    print("5️⃣ Testing Signal Processing...")
    print("-" * 80)
    
    # Test Signal 1: BUY RELIANCE
    print("\n🔔 Signal 1: BUY RELIANCE")
    signal1 = TradingSignal(
        symbol="RELIANCE",
        direction="BUY",
        strength=0.85,
        stop_loss=2450.0,
        take_profit=2550.0,
        strategy_id="EMA_CROSSOVER_001"
    )
    
    order1 = await execution_engine.process_signal(signal1, auto_execute=True)
    
    if order1:
        print(f"✅ Order placed: {order1.order_id}")
        print(f"   Status: {order1.status.value}")
        print(f"   Broker ID: {order1.broker_order_id}")
    else:
        print("❌ Signal rejected")
    
    print()
    
    # Step 6: Check Positions
    print("6️⃣ Checking Positions...")
    print("-" * 80)
    await position_manager.sync_positions()
    
    positions = position_manager.get_all_positions()
    print(f"Open positions: {len(positions)}")
    
    for pos in positions:
        print(f"  • {pos.symbol}: {pos.position_type.value.upper()} {pos.quantity} @ ₹{pos.entry_price:.2f}")
        print(f"    Unrealized P&L: ₹{pos.unrealized_pnl:.2f}")
    
    print()
    
    # Test Signal 2: Duplicate (should be blocked)
    print("\n🔔 Signal 2: BUY RELIANCE (Duplicate - should be blocked)")
    signal2 = TradingSignal(
        symbol="RELIANCE",
        direction="BUY",
        strength=0.90,
        strategy_id="EMA_CROSSOVER_002"
    )
    
    order2 = await execution_engine.process_signal(signal2, auto_execute=True)
    
    if order2:
        print(f"✅ Order placed: {order2.order_id}")
    else:
        print("✅ Signal correctly rejected (duplicate/existing position)")
    
    print()
    
    # Test Signal 3: Different symbol (should succeed)
    print("\n🔔 Signal 3: SELL INFY")
    signal3 = TradingSignal(
        symbol="INFY",
        direction="SELL",
        strength=0.75,
        stop_loss=1520.0,
        take_profit=1480.0,
        strategy_id="RSI_MEAN_REVERSION_001"
    )
    
    order3 = await execution_engine.process_signal(signal3, auto_execute=True)
    
    if order3:
        print(f"✅ Order placed: {order3.order_id}")
    else:
        print("❌ Signal rejected")
    
    print()
    
    # Step 7: Final Statistics
    print("7️⃣ Final Statistics")
    print("="*80)
    
    exec_stats = execution_engine.get_statistics()
    print("\n📊 Execution Engine:")
    print(f"   Signals Received: {exec_stats['signals_received']}")
    print(f"   Signals Executed: {exec_stats['signals_executed']}")
    print(f"   Signals Rejected: {exec_stats['signals_rejected']}")
    print(f"   Success Rate: {exec_stats['success_rate']:.1f}%")
    
    order_stats = order_manager.get_statistics()
    print("\n📋 Order Manager:")
    print(f"   Total Orders: {order_stats['total_orders']}")
    print(f"   Active Orders: {order_stats['active_orders']}")
    print(f"   Completed Orders: {order_stats['completed_orders']}")
    print(f"   Success Rate: {order_stats['success_rate']:.1f}%")
    
    pnl_summary = position_manager.get_pnl_summary()
    print("\n💰 Position Manager:")
    print(f"   Open Positions: {pnl_summary['open_positions']}")
    print(f"   Unrealized P&L: ₹{pnl_summary['unrealized_pnl']:.2f}")
    print(f"   Realized P&L: ₹{pnl_summary['realized_pnl']:.2f}")
    print(f"   Total P&L: ₹{pnl_summary['total_pnl']:.2f}")
    
    balance = await broker.get_balance()
    print("\n💵 Account Balance:")
    print(f"   Available: ₹{balance.available_balance:,.2f}")
    print(f"   Used Margin: ₹{balance.used_margin:,.2f}")
    print(f"   Total: ₹{balance.total_balance:,.2f}")
    
    print()
    print("="*80)
    print("✅ TEST COMPLETED SUCCESSFULLY")
    print("="*80)
    
    # Disconnect
    await broker.disconnect()


if __name__ == "__main__":
    asyncio.run(test_execution_flow())
