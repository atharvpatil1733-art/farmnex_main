import 'package:flutter/material.dart';
import '../../widgets/auto_translated_text.dart';
import 'package:provider/provider.dart';

import '../../core/theme/app_theme.dart';
import '../../models/order_model.dart';
import '../../providers/payment_provider.dart';
import '../../widgets/symbol_widgets.dart';
import '../logistics/track_delivery_button.dart';

class BuyerOrdersScreen extends StatefulWidget {
  final VoidCallback? onBrowse;

  const BuyerOrdersScreen({super.key, this.onBrowse});

  @override
  State<BuyerOrdersScreen> createState() => _BuyerOrdersScreenState();
}

class _BuyerOrdersScreenState extends State<BuyerOrdersScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) context.read<PaymentProvider>().load();
    });
  }

  @override
  Widget build(BuildContext context) {
    final payments = context.watch<PaymentProvider>();
    final orders = payments.orders;

    if (payments.isLoading && orders.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }

    if (payments.lastError != null && orders.isEmpty) {
      return SymbolEmptyState(
        symbol: '⚠️',
        message: payments.lastError!,
        actionLabel: '🔄  Try again',
        onAction: () => payments.load(),
      );
    }

    if (orders.isEmpty) {
      return SymbolEmptyState(
        symbol: '📦',
        message: 'No orders yet.\nBuy a lot to start tracking your money here.',
        actionLabel: '🏪  Browse mandi',
        onAction: widget.onBrowse,
      );
    }

    return RefreshIndicator(
      onRefresh: () => payments.load(keepOld: true),
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        children: [
          Row(
            children: [
              Expanded(
                child: SymbolStat(
                  symbol: '🔒',
                  value: formatRupeesShort(payments.wallet.heldFromMe),
                  caption: 'Held for delivery',
                  color: AppTheme.accentAmber,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: SymbolStat(
                  symbol: '↩️',
                  value: formatRupeesShort(payments.wallet.refunded),
                  caption: 'Refunded',
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: SymbolStat(
                  symbol: '📦',
                  value: '${orders.length}',
                  caption: 'Orders',
                  color: AppTheme.accentTeal,
                ),
              ),
            ],
          ),
          if (payments.lastError != null) ...[
            const SizedBox(height: 10),
            AutoTranslatedText(
              payments.lastError!,
              style: const TextStyle(fontSize: 11.5, color: AppTheme.alertRed, fontWeight: FontWeight.w700),
            ),
          ],
          const SizedBox(height: 20),
          const SectionHeader(symbol: '🧾', title: 'My orders'),
          ...orders.map((order) => _OrderTile(order: order)),
          const SizedBox(height: 20),
        ],
      ),
    );
  }
}

class _OrderTile extends StatefulWidget {
  final OrderModel order;

  const _OrderTile({required this.order});

  @override
  State<_OrderTile> createState() => _OrderTileState();
}

class _OrderTileState extends State<_OrderTile> {
  bool _busy = false;

  Future<void> _pay() async {
    final payments = context.read<PaymentProvider>();
    setState(() => _busy = true);
    final receipt = await payments.payOrder(widget.order.publicId);
    if (receipt != null) await payments.load(keepOld: true);
    if (!mounted) return;
    setState(() => _busy = false);
    _say(receipt != null ? '🔒 Paid (demo). The amount is held until delivery.' : payments.lastError);
  }

  Future<void> _cancel() async {
    final payments = context.read<PaymentProvider>();
    setState(() => _busy = true);
    final ok = await payments.cancelOrder(widget.order.publicId);
    if (!mounted) return;
    setState(() => _busy = false);
    _say(ok ? 'Order cancelled.' : payments.lastError);
  }

  Future<void> _received() async {
    final payments = context.read<PaymentProvider>();
    setState(() => _busy = true);
    final ok = await payments.confirmDelivery(widget.order.publicId);
    if (!mounted) return;
    setState(() => _busy = false);
    _say(ok ? '📦 Thanks! The farmer has been paid.' : payments.lastError);
  }

  void _say(String? message) {
    if (message == null) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: AutoTranslatedText(message)));
  }

  Color get _statusColor {
    final order = widget.order;
    if (order.isCancelled) return AppTheme.alertRed;
    if (order.canPay) return AppTheme.accentAmber;
    return AppTheme.primaryGreen;
  }

  String get _statusSymbol {
    final order = widget.order;
    if (order.isCancelled) return '❌';
    if (order.isDelivered) return '📦';
    if (order.canPay) return '⏳';
    return '🔒';
  }

  @override
  Widget build(BuildContext context) {
    final order = widget.order;
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppTheme.borderLight),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const AutoTranslatedText('🌾', style: TextStyle(fontSize: 22)),
              const SizedBox(width: 8),
              Expanded(
                child: AutoTranslatedText(
                  order.title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w800),
                ),
              ),
              StatusPill(symbol: _statusSymbol, label: order.statusLabel, color: _statusColor),
            ],
          ),
          const SizedBox(height: 8),
          SymbolRow(symbol: '🆔', label: 'Order', value: order.orderNumber),
          for (final line in order.lines)
            SymbolRow(
              symbol: '⚖️',
              label: line.title,
              value: '${_trim(line.quantity)} ${line.unit}',
            ),
          SymbolRow(symbol: '🔒', label: 'Payment', value: order.paymentLabel),
          SymbolRow(
            symbol: '💰',
            label: 'Total',
            value: formatRupees(order.total),
            bold: true,
            valueColor: AppTheme.primaryGreen,
          ),
          if (!order.isCancelled) ...[
            const Divider(height: 18),
            _timeline(order),
          ],
          if (order.canPay || order.canCancel || order.canTrack || order.canConfirmReceived) ...[
            const SizedBox(height: 12),
            Row(
              children: [
                if (order.canPay)
                  Expanded(
                    child: ElevatedButton(
                      onPressed: _busy ? null : _pay,
                      child: const AutoTranslatedText('🔒  Pay (demo)'),
                    ),
                  ),
                if (order.canPay && order.canCancel) const SizedBox(width: 10),
                if (order.canCancel)
                  Expanded(
                    child: OutlinedButton(
                      onPressed: _busy ? null : _cancel,
                      child: const AutoTranslatedText('Cancel'),
                    ),
                  ),
                if (order.canTrack) Expanded(child: TrackDeliveryButton(orderPublicId: order.publicId)),
                if (order.canTrack && order.canConfirmReceived) const SizedBox(width: 10),
                if (order.canConfirmReceived)
                  Expanded(
                    child: ElevatedButton(
                      onPressed: _busy ? null : _received,
                      child: const AutoTranslatedText('📦  Mark as received'),
                    ),
                  ),
              ],
            ),
          ],
        ],
      ),
    );
  }

  static String _trim(double value) => value == value.roundToDouble() ? value.round().toString() : value.toString();

  Widget _timeline(OrderModel order) {
    const steps = ['🧾', '🔒', '🚚', '📦'];
    const labels = ['Placed', 'Paid', 'Transit', 'Delivered'];
    final reached = order.isDelivered
        ? 4
        : order.status == 'SHIPPED'
            ? 3
            : order.isPaid
                ? 2
                : 1;

    return Row(
      children: List.generate(steps.length, (i) {
        final done = i < reached;
        return Expanded(
          child: Column(
            children: [
              Row(
                children: [
                  Expanded(
                    child: Container(
                      height: 2,
                      color: i == 0
                          ? Colors.transparent
                          : (done ? AppTheme.primaryGreen : AppTheme.borderLight),
                    ),
                  ),
                  Opacity(
                    opacity: done ? 1 : 0.32,
                    child: AutoTranslatedText(steps[i], style: const TextStyle(fontSize: 16)),
                  ),
                  Expanded(
                    child: Container(
                      height: 2,
                      color: i == steps.length - 1
                          ? Colors.transparent
                          : (i + 1 < reached ? AppTheme.primaryGreen : AppTheme.borderLight),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 3),
              AutoTranslatedText(
                labels[i],
                style: TextStyle(
                  fontSize: 9,
                  fontWeight: FontWeight.w700,
                  color: done ? AppTheme.primaryGreen : AppTheme.textMuted,
                ),
              ),
            ],
          ),
        );
      }),
    );
  }
}
