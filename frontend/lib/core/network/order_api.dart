import 'package:dio/dio.dart';

import '../../models/order_model.dart';
import '../config/api_config.dart';
import 'api_client.dart';
import 'listing_api.dart' show listingErrorMessage;

/// Orders. The buyer only sends listing ids + quantities; prices, totals, status and the buyer
/// come from the server (the buyer from the login token).
class OrderApi {
  final Dio _dio = ApiClient().dio;

  /// Check out a cart. The server makes one order per farmer, all or nothing.
  Future<List<OrderModel>> checkout(List<({String listingId, num quantity})> lines) async {
    final response = await _dio.post<dynamic>(ApiConfig.ordersEndpoint, data: {
      'items': [
        for (final l in lines) {'listing_id': l.listingId, 'quantity': l.quantity.toString()},
      ],
    });
    final orders = (response.data as Map<String, dynamic>)['orders'] as List<dynamic>;
    return orders.map((e) => OrderModel.fromJson(e as Map<String, dynamic>)).toList();
  }

  /// My orders (as buyer or as seller).
  Future<List<OrderModel>> list() async {
    final response = await _dio.get<dynamic>(ApiConfig.ordersEndpoint, queryParameters: {'limit': 100});
    return (response.data as List<dynamic>).map((e) => OrderModel.fromJson(e as Map<String, dynamic>)).toList();
  }

  /// Every item I can see, grouped by the order's public id.
  Future<Map<String, List<OrderLine>>> itemsByOrder() async {
    final response = await _dio.get<dynamic>(ApiConfig.orderItemsEndpoint, queryParameters: {'limit': 100});
    final grouped = <String, List<OrderLine>>{};
    for (final row in response.data as List<dynamic>) {
      final json = row as Map<String, dynamic>;
      grouped.putIfAbsent(json['order_id'].toString(), () => []).add(OrderLine.fromJson(json));
    }
    return grouped;
  }

  /// The buyer cancels an order that is still PLACED.
  Future<OrderModel> cancel(String orderId) async {
    final response = await _dio.patch<dynamic>(ApiConfig.orderEndpoint(orderId), data: {'status': 'CANCELLED'});
    return OrderModel.fromJson(response.data as Map<String, dynamic>);
  }

  /// The buyer says the goods arrived (after the driver finished the last stop). The server then
  /// marks the order delivered and pays the farmer.
  Future<void> confirmDelivery(String orderId) async {
    await _dio.post<dynamic>(ApiConfig.confirmDeliveryEndpoint(orderId));
  }
}

String orderErrorMessage(Object error) => listingErrorMessage(error);
