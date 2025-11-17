const ACCESS_TOKEN_KEYS = ['abkms_token', 'wikl_token'] as const;
const ACCESS_TOKEN_EXPIRY_KEYS = ['abkms_token_expiry', 'wikl_token_expiry'] as const;
const REFRESH_TOKEN_KEYS = ['abkms_refresh_token', 'wikl_refresh_token'] as const;
const REFRESH_TOKEN_EXPIRY_KEYS = ['abkms_refresh_token_expiry', 'wikl_refresh_token_expiry'] as const;
const USER_INFO_KEYS = ['abkms_user', 'wikl_user'] as const;

const setValueForKeys = (keys: readonly string[], value: string | null | undefined) => {
  keys.forEach((key) => {
    if (value === null || value === undefined) {
      localStorage.removeItem(key);
    } else {
      localStorage.setItem(key, value);
    }
  });
};

const getValueFromKeys = (keys: readonly string[]): string | null => {
  for (const key of keys) {
    const value = localStorage.getItem(key);
    if (value) {
      return value;
    }
  }
  return null;
};

export const setAccessToken = (token: string | null | undefined) => {
  setValueForKeys(ACCESS_TOKEN_KEYS, token);
};

export const getAccessToken = (): string | null => {
  return getValueFromKeys(ACCESS_TOKEN_KEYS);
};

export const clearAccessToken = () => {
  setAccessToken(null);
};

export const setAccessTokenExpiry = (expiry: string | null | undefined) => {
  setValueForKeys(ACCESS_TOKEN_EXPIRY_KEYS, expiry);
};

export const getAccessTokenExpiry = (): string | null => {
  return getValueFromKeys(ACCESS_TOKEN_EXPIRY_KEYS);
};

export const clearAccessTokenExpiry = () => {
  setAccessTokenExpiry(null);
};

export const setRefreshToken = (token: string | null | undefined) => {
  setValueForKeys(REFRESH_TOKEN_KEYS, token);
};

export const getRefreshToken = (): string | null => {
  return getValueFromKeys(REFRESH_TOKEN_KEYS);
};

export const clearRefreshToken = () => {
  setRefreshToken(null);
};

export const setRefreshTokenExpiry = (expiry: string | null | undefined) => {
  setValueForKeys(REFRESH_TOKEN_EXPIRY_KEYS, expiry);
};

export const getRefreshTokenExpiry = (): string | null => {
  return getValueFromKeys(REFRESH_TOKEN_EXPIRY_KEYS);
};

export const clearRefreshTokenExpiry = () => {
  setRefreshTokenExpiry(null);
};

export const setUserInfo = (userInfo: string | null | undefined) => {
  setValueForKeys(USER_INFO_KEYS, userInfo);
};

export const getUserInfo = (): string | null => {
  return getValueFromKeys(USER_INFO_KEYS);
};

export const clearUserInfo = () => {
  setUserInfo(null);
};

export const clearAllAuthStorage = () => {
  clearAccessToken();
  clearAccessTokenExpiry();
  clearRefreshToken();
  clearRefreshTokenExpiry();
  clearUserInfo();
};
