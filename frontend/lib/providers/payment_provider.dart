import 'package:flutter/material.dart';

import '../core/network/order_api.dart';
import '../core/network/payment_api.dart';
import '../models/order_model.dart';

/// Orders, Pay (demo) and the demo wallet, all read from the backend. No real money moves: the
/// server works out every amount, holds it until delivery and releases it to the farmer.
class PaymentProvider extends ChangeNotifier {
  PaymentProvider({OrderApi? orderApi, PaymentApi? paymentApi})
      : _orderApi = orderApi ?? OrderApi(),
        _paymentApi = paymentApi ?? PaymentApi();

  final OrderApi _orderApi;
  final PaymentApi _paymentApi;

  List<OrderModel> _orders = [];
  WalletSummary _wallet = const WalletSummary();
  bool _isLoading = false;
  bool _isProcessing = false;
  String? _lastError;

  bool get isLoading => _isLoading;
  bool get isProcessing => _isProcessing;
  String? get lastError => _lastError;

  List<OrderModel> get orders => List.unmodifiable(_orders);
  WalletSummary get wallet => _wallet;

  /// Money released to me on delivery (the profile card calls this the wallet balance).
  double get walletBalance => _wallet.received;

  /// Money held until delivery: what I paid plus what is held for my sales.
  double get moneyInEscrow => _wallet.heldFromMe + _wallet.heldForMe;

  double get lifetimeSettled => _wallet.received;

  String orderNumberFor(String orderId) {
    for (final o in _orders) {
      if (o.publicId == orderId) return o.orderNumber;
    }
    return '';
  }

  /// Reload orders, their items, my payments and the wallet. `keepOld` keeps what is on screen while
  /// refreshing; a first load clears it so one person never sees another person's data.
  Future<void> load({bool keepOld = false}) async {
    _isLoading = true;
    _lastError = null;
    if (!keepOld) {
      _orders = [];
      _wallet = const WalletSummary();
    }
    notifyListeners();
    try {
      final results = await Future.wait<dynamic>([
        _orderApi.list(),
        _orderApi.itemsByOrder(),
        _paymentApi.list(),
        _paymentApi.wallet(),
      ]);
      final orders = results[0] as List<OrderModel>;
      final items = results[1] as Map<String, List<OrderLine>>;
      final payments = results[2] as List<PaymentReceipt>;
      _wallet = results[3] as WalletSummary;

      final paymentStatus = <String, String>{};
      for (final p in payments) {
        final current = paymentStatus[p.orderId];
        if (_rank(p.status) > _rank(current)) paymentStatus[p.orderId] = p.status;
      }
      _orders = [
        for (final o in orders)
          o.withDetails(lines: items[o.publicId] ?? const [], paymentStatus: paymentStatus[o.publicId]),
      ];
    } catch (e) {
      _lastError = orderErrorMessage(e);
      if (!keepOld) {
        _orders = [];
        _wallet = const WalletSummary();
      }
    }
    _isLoading = false;
    notifyListeners();
  }

  static int _rank(String? status) {
    switch (status) {
      case 'RELEASED':
        return 3;
      case 'REFUNDED':
        return 2;
      case 'HELD':
        return 1;
      default:
        return 0;
    }
  }

  /// Step 1 of checkout: the server turns the cart into orders (one per farmer). Returns null and
  /// sets [lastError] if it could not.
  Future<List<OrderModel>?> placeOrders(List<({String listingId, num quantity})> lines) async {
    _isProcessing = true;
    _lastError = null;
    notifyListeners();
    try {
      return await _orderApi.checkout(lines);
    } catch (e) {
      _lastError = orderErrorMessage(e);
      return null;
    } finally {
      _isProcessing = false;
      notifyListeners();
    }
  }

  /// Step 2: Pay (demo) one order. Paying twice returns the same payment.
  Future<PaymentReceipt?> payOrder(String orderId) async {
    _isProcessing = true;
    _lastError = null;
    notifyListeners();
    try {
      final receipt = await _paymentApi.payDemo(orderId, idempotencyKey: 'pay-$orderId');
      return receipt;
    } catch (e) {
      _lastError = paymentErrorMessage(e);
      return null;
    } finally {
      _isProcessing = false;
      notifyListeners();
    }
  }

  /// The buyer cancels an order that is still waiting for payment. Returns true when it worked.
  Future<bool> cancelOrder(String orderId) async {
    _lastError = null;
    try {
      await _orderApi.cancel(orderId);
    } catch (e) {
      _lastError = orderErrorMessage(e);
      notifyListeners();
      return false;
    }
    await load(keepOld: true);
    return true;
  }

  /// The buyer confirms the goods arrived; the server then pays the farmer. Returns true when it worked.
  /// Fails with the server's message while the driver has not finished the last stop.
  Future<bool> confirmDelivery(String orderId) async {
    _lastError = null;
    try {
      await _orderApi.confirmDelivery(orderId);
    } catch (e) {
      _lastError = orderErrorMessage(e);
      notifyListeners();
      return false;
    }
    await load(keepOld: true);
    return true;
  }

  /// Kept so older callers compile. Money is released by the server once the driver finished the
  /// last stop and the buyer confirmed (confirmDelivery), never directly from the app.
  void releaseEscrow(String orderId) {}

  void clearError() {
    _lastError = null;
    notifyListeners();
  }
}
