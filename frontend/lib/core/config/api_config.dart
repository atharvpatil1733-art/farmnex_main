
class ApiConfig {
  static const String baseUrl = 'https://farmnex-a.fastapicloud.dev';
  static const String wsBaseUrl = 'wss://farmnex-a.fastapicloud.dev';

  static const String healthEndpoint = '/health';
  static const String databaseHealthEndpoint = '/db';
  static const String readinessEndpoint = '/ready';

  static const String registerRequestOtpEndpoint = '/api/v2/auth/register/request-otp';
  static const String registerResendOtpEndpoint = '/api/v2/auth/register/resend';
  static const String registerVerifyOtpEndpoint = '/api/v2/auth/register/verify';
  static const String registerCompleteEndpoint = '/api/v2/auth/register/complete';
  static const String loginRequestOtpEndpoint = '/api/v2/auth/login/request-otp';
  static const String loginResendOtpEndpoint = '/api/v2/auth/login/resend';
  static const String loginVerifyOtpEndpoint = '/api/v2/auth/login/verify';
  static const String refreshTokenEndpoint = '/api/v2/auth/refresh';
  static const String logoutEndpoint = '/api/v2/auth/logout';

  static const String usersEndpoint = '/api/v2/users';
  static const String myProfileEndpoint = '/api/v2/users/me';
  static const String myProfileImageEndpoint = '/api/v2/users/me/image';
  static String userEndpoint(String publicId) => '$usersEndpoint/$publicId';

  static const String addressesEndpoint = '/api/v2/addresses';
  static String addressEndpoint(String publicId) => '$addressesEndpoint/$publicId';
  static String defaultAddressEndpoint(String publicId) => '${addressEndpoint(publicId)}/default';
  static String deactivateAddressEndpoint(String publicId) => '${addressEndpoint(publicId)}/deactivate';
  static String activateAddressEndpoint(String publicId) => '${addressEndpoint(publicId)}/activate';

  static const String farmsEndpoint = '/api/v2/farms';
  static String farmEndpoint(String publicId) => '$farmsEndpoint/$publicId';
  static String farmFileEndpoint(String publicId) => '${farmEndpoint(publicId)}/file';
  static String farmFileDownloadEndpoint(String publicId) => '${farmFileEndpoint(publicId)}/download';

  static const String verificationUploadEndpoint = '/api/verification/upload';
  static const String aiChatEndpoint = '/api/ai/chat';

  // Old URLs below do not exist on the backend yet. Each sits in the section of the feature that
  // will replace it. A later session edits only between its own two marker lines.

  // >>> listing >>>
  // Old URL, not on the backend. Kept only because the bidding section below still builds on it (S27).
  static const String cropsEndpoint = '/api/crops';
  static const String productListingsEndpoint = '/api/v2/product-listings';
  static String productListingEndpoint(String publicId) => '$productListingsEndpoint/$publicId';
  static const String cropTypesEndpoint = '/api/v2/crop-types';
  static const String farmCropsEndpoint = '/api/v2/farm-crops';
  static const String cropBatchesEndpoint = '/api/v2/crop-batches';
  // <<< listing <<<

  // >>> market >>>
  // The market reads productListingsEndpoint (listing section above); it has no URL of its own.
  // <<< market <<<

  // >>> cart >>>
  // The cart lives in the app; "check out" is a POST on ordersEndpoint (payment section below).
  // <<< cart <<<

  // >>> payment >>>
  static const String ordersEndpoint = '/api/v2/orders';
  static String orderEndpoint(String publicId) => '$ordersEndpoint/$publicId';
  static const String orderItemsEndpoint = '/api/v2/order-items';
  static const String paymentsEndpoint = '/api/v2/payments';
  static const String walletEndpoint = '/api/v2/payments/wallet';
  static String payDemoEndpoint(String orderId) => '$paymentsEndpoint/orders/$orderId/pay-demo';
  static String confirmDeliveryEndpoint(String orderId) => '/api/v2/logistics/orders/$orderId/confirm-delivery';
  // <<< payment <<<

  // >>> bidding >>>
  // Dead: only the unused websocket_service.dart reads it (that file is not in S27's row, so it stays).
  static String cropBidsWsUrl(String cropId) => '$wsBaseUrl/ws/bidding/$cropId';
  static const String bidEventsEndpoint = '/api/v2/bid-events';
  static const String bidsEndpoint = '/api/v2/bids';
  static String bidAcceptEndpoint(String bidId) => '$bidsEndpoint/$bidId/accept';
  // <<< bidding <<<

  // >>> rescue >>>
  static const String rescueCropsEndpoint = '/api/v2/rescue/crops';
  static const String rescueLotsEndpoint = '/api/v2/rescue/lots';
  static String rescueLotEndpoint(String lotId) => '$rescueLotsEndpoint/$lotId';
  static String rescueLotMatchesEndpoint(String lotId) => '${rescueLotEndpoint(lotId)}/matches';
  static String rescueLotSoldEndpoint(String lotId) => '${rescueLotEndpoint(lotId)}/sold';
  static const String rescueSimulateEndpoint = '/api/v2/rescue/simulate';
  static const String rescueAlertsEndpoint = '/api/v2/rescue/alerts';
  static String rescueAlertReadEndpoint(String alertId) => '$rescueAlertsEndpoint/$alertId/read';
  // <<< rescue <<<

  // >>> forecast >>>
  static const String forecastMetaEndpoint = '/api/v2/forecast/meta';
  static const String forecastPriceEndpoint = '/api/v2/forecast/price';
  static const String forecastDemandEndpoint = '/api/v2/forecast/demand';
  // <<< forecast <<<

  // >>> logistics >>>
  static const String logisticsVehiclesEndpoint = '/api/v2/logistics/vehicles';
  static const String logisticsMyVehiclesEndpoint = '/api/v2/logistics/my-vehicles';
  static const String routesBase = '/api/v2/routes';
  static String routesVehicleStatusEndpoint(String id) => '$routesBase/vehicles/$id/status';
  static String routesVehicleLocationEndpoint(String id) => '$routesBase/vehicles/$id/location';
  static String routesVehicleTripEndpoint(String id) => '$routesBase/vehicles/$id/current-trip';
  static String routesVehicleBackhaulEndpoint(String id) => '$routesBase/vehicles/$id/backhaul';
  static String routesAcceptLoadEndpoint(String vehicleId, String loadId) =>
      '$routesBase/vehicles/$vehicleId/accept-load/$loadId';
  static const String routesPlanTripEndpoint = '$routesBase/trips/plan';
  static String routesTripStartEndpoint(String id) => '$routesBase/trips/$id/start';
  static String routesTripCancelEndpoint(String id) => '$routesBase/trips/$id/cancel';
  static String routesStopCompleteEndpoint(String tripId, String stopId) =>
      '$routesBase/trips/$tripId/stops/$stopId/complete';
  static String routesOrderDeliveryEndpoint(String orderId) => '$routesBase/orders/$orderId/delivery';
  // <<< logistics <<<

  // >>> waste >>>
  static const String wasteRecordsEndpoint = '/api/v2/waste-records';
  static const String wasteListingsEndpoint = '/api/v2/waste-utilization-listings';
  static String wasteListingEndpoint(String publicId) => '$wasteListingsEndpoint/$publicId';
  // <<< waste <<<

  // >>> voice >>>
  // <<< voice <<<
}
