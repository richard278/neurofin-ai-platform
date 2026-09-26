import { apiRequest } from './client';

interface AccessTokenResponse {
  access_token: string;
  token_type: 'bearer';
  expires_in: number;
}

let accessToken: string | null = null;

const csrfHeaders = {
  'X-NeuroFin-CSRF': '1',
};

export function getRuntimeAccessToken(): string | null {
  return accessToken;
}

export async function login(
  email: string,
  password: string,
): Promise<void> {
  const result = await apiRequest<AccessTokenResponse>(
    '/auth/login',
    {
      method: 'POST',
      credentials: 'include',
      headers: csrfHeaders,
      body: JSON.stringify({
        email,
        password,
      }),
    },
  );

  accessToken = result.access_token;
}

export async function refreshSession(): Promise<void> {
  const result = await apiRequest<AccessTokenResponse>(
    '/auth/refresh',
    {
      method: 'POST',
      credentials: 'include',
      headers: csrfHeaders,
    },
  );

  accessToken = result.access_token;
}

export async function logout(): Promise<void> {
  try {
    await apiRequest<void>(
      '/auth/logout',
      {
        method: 'POST',
        credentials: 'include',
        headers: csrfHeaders,
      },
    );
  } finally {
    accessToken = null;
  }
}
