import { z } from 'zod';

export const loginRequestSchema = z.object({
  username: z.string().min(1),
  password: z.string().min(1),
});
export type LoginRequest = z.infer<typeof loginRequestSchema>;

export const currentUserSchema = z.object({
  name: z.string(),
  role: z.string(),
  initials: z.string(),
});
export type CurrentUser = z.infer<typeof currentUserSchema>;

export const loginResponseSchema = z.object({
  token: z.string(),
  user: currentUserSchema,
});
export type LoginResponse = z.infer<typeof loginResponseSchema>;
