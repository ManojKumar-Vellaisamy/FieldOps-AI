/**
 * Utility functions for extracting and formatting API errors,
 * specifically handling FastAPI/Pydantic validation error structures.
 */

export interface FormErrorState {
  title: string;
  messages: string[];
}

interface PydanticErrorItem {
  type?: string;
  loc?: (string | number)[];
  msg?: string;
  input?: unknown;
  ctx?: Record<string, unknown>;
}

const FIELD_LABEL_MAP: Record<string, string> = {
  customer_name: 'Customer name',
  customer_phone: 'Customer phone',
  address: 'Address',
  latitude: 'Latitude',
  longitude: 'Longitude',
  required_skill_id: 'Required skill',
  priority: 'Priority',
  scheduled_time: 'Scheduled time',
  description: 'Description',
  service_instructions: 'Service instructions',
  reason: 'Cancellation reason',
  notes: 'Notes',
};

/** Convert a field identifier from Pydantic `loc` to a user-friendly label */
function getFieldLabel(loc?: (string | number)[]): string {
  if (!loc || loc.length === 0) return 'Field';
  // Pydantic loc is typically ['body', 'field_name'] or ['query', 'field_name']
  const relevantParts = loc.filter((part) => part !== 'body' && part !== 'query' && part !== 'path');
  const rawField = String(relevantParts[relevantParts.length - 1] ?? loc[loc.length - 1]);

  if (FIELD_LABEL_MAP[rawField]) {
    return FIELD_LABEL_MAP[rawField];
  }

  // Convert snake_case to readable words
  return rawField
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Formats a single Pydantic validation error item into a clear human-readable string */
function formatValidationErrorItem(item: PydanticErrorItem): string {
  const fieldLabel = getFieldLabel(item.loc);
  const rawMsg = item.msg || '';
  const cleanedMsg = rawMsg.replace(/^(Value error|Assertion failed),\s*/i, '').trim();

  // Handle specific Pydantic error types
  if (item.type === 'missing') {
    return `${fieldLabel} is required.`;
  }

  if (item.type === 'uuid_parsing') {
    return `${fieldLabel} must be a valid selection.`;
  }

  if (item.type?.startsWith('datetime')) {
    return `${fieldLabel} must be a valid date and time.`;
  }

  if (item.type === 'less_than_equal' && item.ctx?.le !== undefined) {
    if (fieldLabel.toLowerCase() === 'latitude') {
      return 'Latitude must be between -90 and 90.';
    }
    if (fieldLabel.toLowerCase() === 'longitude') {
      return 'Longitude must be between -180 and 180.';
    }
    return `${fieldLabel} must be less than or equal to ${item.ctx.le}.`;
  }

  if (item.type === 'greater_than_equal' && item.ctx?.ge !== undefined) {
    if (fieldLabel.toLowerCase() === 'latitude') {
      return 'Latitude must be between -90 and 90.';
    }
    if (fieldLabel.toLowerCase() === 'longitude') {
      return 'Longitude must be between -180 and 180.';
    }
    return `${fieldLabel} must be greater than or equal to ${item.ctx.ge}.`;
  }

  if (item.type === 'string_too_short' && item.ctx?.min_length !== undefined) {
    return `${fieldLabel} must have at least ${item.ctx.min_length} characters.`;
  }

  if (item.type === 'string_too_long' && item.ctx?.max_length !== undefined) {
    return `${fieldLabel} cannot exceed ${item.ctx.max_length} characters.`;
  }

  if (cleanedMsg) {
    // If the message already contains the field label, capitalise first letter
    if (cleanedMsg.toLowerCase().includes(fieldLabel.toLowerCase())) {
      return cleanedMsg.charAt(0).toUpperCase() + cleanedMsg.slice(1);
    }
    return `${fieldLabel}: ${cleanedMsg.charAt(0).toUpperCase() + cleanedMsg.slice(1)}`;
  }

  return `${fieldLabel} is invalid.`;
}

/**
 * Extracts and normalizes any API error (FastAPI validation, custom FieldOpsException, AxiosError)
 * into a safe, strongly-typed `FormErrorState` that can never crash React by rendering raw objects.
 */
export function parseApiError(err: unknown, defaultTitle = 'Unable to complete request'): FormErrorState {
  if (!err) {
    return { title: defaultTitle, messages: ['An unexpected error occurred. Please try again.'] };
  }

  // If already a FormErrorState
  if (typeof err === 'object' && 'title' in err && 'messages' in err && Array.isArray((err as any).messages)) {
    return err as FormErrorState;
  }

  // If passed a simple string
  if (typeof err === 'string') {
    return { title: defaultTitle, messages: [err] };
  }

  const errorObj = err as any;
  const responseData = errorObj?.response?.data;

  // 1. Custom backend error format: { error: { code: '...', message: '...' } }
  if (responseData?.error?.message && typeof responseData.error.message === 'string') {
    return {
      title: defaultTitle,
      messages: [responseData.error.message],
    };
  }

  // 2. FastAPI validation errors: { detail: [ { type, loc, msg, input, ctx } ] }
  if (responseData?.detail) {
    if (Array.isArray(responseData.detail)) {
      const messages: string[] = [];
      const seen = new Set<string>();

      for (const item of responseData.detail) {
        if (item && typeof item === 'object') {
          const formatted = formatValidationErrorItem(item as PydanticErrorItem);
          if (!seen.has(formatted)) {
            seen.add(formatted);
            messages.push(formatted);
          }
        } else if (typeof item === 'string') {
          if (!seen.has(item)) {
            seen.add(item);
            messages.push(item);
          }
        }
      }

      return {
        title: defaultTitle,
        messages: messages.length > 0 ? messages : ['Validation failed. Please check your inputs.'],
      };
    }

    // 3. FastAPI HTTPException: { detail: 'string message' }
    if (typeof responseData.detail === 'string') {
      return {
        title: defaultTitle,
        messages: [responseData.detail],
      };
    }

    // 4. FastAPI HTTPException with object detail
    if (typeof responseData.detail === 'object') {
      const detailMsg =
        responseData.detail.message ||
        responseData.detail.msg ||
        responseData.detail.error ||
        null;
      if (typeof detailMsg === 'string') {
        return { title: defaultTitle, messages: [detailMsg] };
      }
    }
  }

  // 5. Generic response message
  if (typeof responseData?.message === 'string') {
    return {
      title: defaultTitle,
      messages: [responseData.message],
    };
  }

  // 6. Axios Error message or native Error message
  if (errorObj?.message && typeof errorObj.message === 'string') {
    if (errorObj.message === 'Network Error') {
      return { title: 'Network Error', messages: ['Unable to connect to the server. Please check your connection.'] };
    }
    return { title: defaultTitle, messages: [errorObj.message] };
  }

  return { title: defaultTitle, messages: ['An unexpected error occurred. Please try again.'] };
}

/**
 * Returns a single formatted error string from any API error, suitable for notices or logs.
 */
export function formatApiErrorMessage(err: unknown, fallback = 'An unexpected error occurred.'): string {
  const parsed = parseApiError(err, fallback);
  if (parsed.messages.length === 1 && parsed.messages[0]) {
    return parsed.messages[0];
  }
  return parsed.messages.length > 0
    ? `${parsed.title}: ${parsed.messages.join(' ')}`
    : fallback;
}
