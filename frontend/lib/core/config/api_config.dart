
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
  static const String cropsEndpoint = '/api/crops';
  // <<< listing <<<

  // >>> market >>>
  // <<< market <<<

  // >>> cart >>>
  // <<< cart <<<

  // >>> payment >>>
  // <<< payment <<<

  // >>> bidding >>>
  static String cropBidsWsUrl(String cropId) => '$wsBaseUrl/ws/bidding/$cropId';
  static String cropBidsEndpoint(String cropId) => '$cropsEndpoint/$cropId/bids';
  // <<< bidding <<<

  // >>> rescue >>>
  static const String cropRescueEndpoint = '/api/rescue/request';
  // <<< rescue <<<

  // >>> forecast >>>
  static const String aiPricePredictionEndpoint = '/api/ai/price-prediction';
  static String cropPricePredictionEndpoint(String cropId) => '$aiPricePredictionEndpoint/$cropId';
  // <<< forecast <<<

  // >>> logistics >>>
  // <<< logistics <<<

  // >>> waste >>>
  static const String wasteListingsEndpoint = '/api/waste/listings';
  // <<< waste <<<

  // >>> voice >>>
  // <<< voice <<<
}
