// Orders, payments and the wallet as the backend sends them (snake_case JSON, Decimal as string).

double _num(dynamic value) => value == null ? 0 : double.tryParse(value.toString()) ?? 0;

DateTime? _date(dynamic value) => value == null ? null : DateTime.tryParse(value.toString())?.toLocal();

class OrderLine {
  final String publicId;
  final String title;
  final double quantity;
  final String unit;
  final double unitPrice;
  final double lineTotal;
  final String status;

  const OrderLine({
    required this.publicId,
    required this.title,
    required this.quantity,
    required this.unit,
    required this.unitPrice,
    required this.lineTotal,
    required this.status,
  });

  factory OrderLine.fromJson(Map<String, dynamic> json) => OrderLine(
        publicId: json['public_id'].toString(),
        title: (json['title_snapshot'] ?? '').toString(),
        quantity: _num(json['quantity']),
        unit: (json['unit'] ?? '').toString(),
        unitPrice: _num(json['unit_price']),
        lineTotal: _num(json['line_total']),
        status: (json['status'] ?? '').toString(),
      );
}

class OrderModel {
  final String publicId;
  final String orderNumber;
  final String status;
  final double subtotal;
  final double deliveryFee;
  final double total;
  final String? deliveryCity;
  final DateTime? placedAt;
  final List<OrderLine> lines;

  /// HELD, RELEASED or REFUNDED from the buyer's latest payment; null = not paid yet.
  final String? paymentStatus;

  const OrderModel({
    required this.publicId,
    required this.orderNumber,
    required this.status,
    required this.subtotal,
    required this.deliveryFee,
    required this.total,
    this.deliveryCity,
    this.placedAt,
    this.lines = const [],
    this.paymentStatus,
  });

  factory OrderModel.fromJson(Map<String, dynamic> json) {
    final address = json['delivery_address_snapshot'];
    return OrderModel(
      publicId: json['public_id'].toString(),
      orderNumber: (json['order_number'] ?? '').toString(),
      status: (json['status'] ?? '').toString(),
      subtotal: _num(json['subtotal']),
      deliveryFee: _num(json['delivery_fee']),
      total: _num(json['total_amount']),
      deliveryCity: address is Map ? address['city']?.toString() : null,
      placedAt: _date(json['placed_at'] ?? json['created_at']),
    );
  }

  OrderModel withDetails({required List<OrderLine> lines, String? paymentStatus}) => OrderModel(
        publicId: publicId,
        orderNumber: orderNumber,
        status: status,
        subtotal: subtotal,
        deliveryFee: deliveryFee,
        total: total,
        deliveryCity: deliveryCity,
        placedAt: placedAt,
        lines: lines,
        paymentStatus: paymentStatus,
      );

  bool get isCancelled => status == 'CANCELLED';
  bool get isDelivered => status == 'DELIVERED';
  bool get isPaid => paymentStatus == 'HELD' || paymentStatus == 'RELEASED';

  /// Still waiting for the buyer to pay (and not cancelled or expired).
  bool get canPay => status == 'PLACED' && paymentStatus == null;
  bool get canCancel => status == 'PLACED';

  /// The buyer may confirm receipt once the order is paid and underway; the server refuses (with a
  /// message) until the driver has finished the last stop.
  bool get canConfirmReceived => isPaid && !isCancelled && !isDelivered && status != 'PLACED';

  /// A truck can only be booked once the farmer confirmed the order.
  bool get canTrack => !isCancelled && status != 'PLACED';

  String get title => lines.isEmpty
      ? orderNumber
      : lines.length == 1
          ? lines.first.title
          : '${lines.first.title} +${lines.length - 1}';

  String get statusLabel {
    switch (status) {
      case 'PLACED':
        return canPay ? 'Waiting for payment' : 'Placed';
      case 'CONFIRMED':
        return 'Confirmed';
      case 'SHIPPED':
        return 'On the way';
      case 'DELIVERED':
        return 'Delivered';
      case 'CANCELLED':
        return 'Cancelled';
      default:
        return status.isEmpty ? 'Placed' : status[0] + status.substring(1).toLowerCase();
    }
  }

  String get paymentLabel {
    switch (paymentStatus) {
      case 'HELD':
        return 'Held until delivery';
      case 'RELEASED':
        return 'Paid to the farmer';
      case 'REFUNDED':
        return 'Refunded';
      default:
        return 'Not paid';
    }
  }
}

class PaymentReceipt {
  final String publicId;
  final String orderId;
  final double amount;
  final String status;
  final DateTime? paidAt;

  const PaymentReceipt({
    required this.publicId,
    required this.orderId,
    required this.amount,
    required this.status,
    this.paidAt,
  });

  factory PaymentReceipt.fromJson(Map<String, dynamic> json) => PaymentReceipt(
        publicId: json['public_id'].toString(),
        orderId: json['order_id'].toString(),
        amount: _num(json['amount']),
        status: (json['status'] ?? '').toString(),
        paidAt: _date(json['paid_at'] ?? json['created_at']),
      );
}

class WalletEntry {
  final String publicId;
  final String type; // HOLD, RELEASE or REFUND
  final double amount;
  final String orderId;
  final DateTime? createdAt;

  const WalletEntry({
    required this.publicId,
    required this.type,
    required this.amount,
    required this.orderId,
    this.createdAt,
  });

  factory WalletEntry.fromJson(Map<String, dynamic> json) => WalletEntry(
        publicId: json['public_id'].toString(),
        type: (json['entry_type'] ?? '').toString(),
        amount: _num(json['amount']),
        orderId: json['order_id'].toString(),
        createdAt: _date(json['created_at']),
      );

  /// Money that comes to me (released sale money, refunds). A HOLD is money I paid.
  bool get isCredit => type != 'HOLD';
}

/// The demo wallet (no real money).
class WalletSummary {
  final double heldFromMe;
  final double heldForMe;
  final double received;
  final double refunded;
  final List<WalletEntry> entries;

  const WalletSummary({
    this.heldFromMe = 0,
    this.heldForMe = 0,
    this.received = 0,
    this.refunded = 0,
    this.entries = const [],
  });

  factory WalletSummary.fromJson(Map<String, dynamic> json) => WalletSummary(
        heldFromMe: _num(json['held_from_me']),
        heldForMe: _num(json['held_for_me']),
        received: _num(json['received']),
        refunded: _num(json['refunded']),
        entries: ((json['entries'] as List<dynamic>?) ?? const [])
            .map((e) => WalletEntry.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
}
