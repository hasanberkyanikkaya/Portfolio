import { useMutation, useQueryClient } from '@tanstack/react-query'
import { closePosition, createPosition, deletePosition } from '../api/positions'
import { runPredictions } from '../api/predictions'
import { submitRiskProfile } from '../api/riskProfile'
import type { ApiError } from '../api/client'
import type {
  PositionCloseRequest,
  PositionCreate,
  PositionResponse,
  PredictionsRunResponse,
  RealizedTradeResponse,
  RiskProfileIn,
  RiskProfileOut,
} from '../types/api'

export function useAddPosition() {
  const queryClient = useQueryClient()
  return useMutation<PositionResponse, ApiError, PositionCreate>({
    mutationFn: createPosition,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['positions'] })
    },
  })
}

export function useClosePosition() {
  const queryClient = useQueryClient()
  return useMutation<
    RealizedTradeResponse,
    ApiError,
    { id: number; body: PositionCloseRequest }
  >({
    mutationFn: ({ id, body }) => closePosition(id, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['positions'] })
      queryClient.invalidateQueries({ queryKey: ['realized'] })
    },
  })
}

export function useDeletePosition() {
  const queryClient = useQueryClient()
  return useMutation<void, ApiError, number>({
    mutationFn: deletePosition,
    // onSettled so a 404 (already-deleted row) still resyncs the list.
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['positions'] })
    },
  })
}

export function useRunPredictions() {
  const queryClient = useQueryClient()
  return useMutation<PredictionsRunResponse, ApiError, void>({
    mutationFn: runPredictions,
    onSuccess: () => {
      // Prefix match also invalidates every ['predictions', ticker] query.
      queryClient.invalidateQueries({ queryKey: ['predictions'] })
    },
  })
}

export function useSubmitRiskProfile() {
  const queryClient = useQueryClient()
  return useMutation<RiskProfileOut, ApiError, RiskProfileIn>({
    mutationFn: submitRiskProfile,
    onSuccess: (data) => {
      queryClient.setQueryData(['risk-profile'], data)
    },
  })
}
