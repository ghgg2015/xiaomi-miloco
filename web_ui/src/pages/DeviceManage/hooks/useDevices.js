/**
 * Copyright (C) 2025 Xiaomi Corporation
 * This software may be used and distributed according to the terms of the Xiaomi Miloco License Agreement.
 */

import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { getCameraList, refreshMiotCamera, createRtspSource, deleteRtspSource } from '@/api';
import { message } from 'antd';

export const useDevices = () => {
  const { t } = useTranslation();
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchDevices = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await getCameraList();

      if (response.code === 0) {
        // sort by order: online but not set password > online and set password > offline and set password > offline and not set password
        const sortedDevices = response.data.sort((a, b) => {
          // get device type weight
          const getDeviceWeight = (device) => {
            if (device.source_type === 'rtsp' && device.online) {
              return 0;
            } else if (device.online && device.is_set_pincode <= 0) {
              return 1;
            } else if (device.online && device.is_set_pincode > 0) {
              return 2;
            } else if (!device.online && device.is_set_pincode > 0) {
              return 3;
            } else {
              return 4;
            }
          };

          const weightA = getDeviceWeight(a);
          const weightB = getDeviceWeight(b);

          return weightA - weightB;
        });
        setDevices(sortedDevices || []);
      } else {
        setError(response.message || t('deviceManage.fetchDeviceListFailed'));
      }
    } catch (err) {
      setError(t('deviceManage.fetchDeviceListFailed'));
      console.error('fetchDeviceListFailed:', err);
    } finally {
      setLoading(false);
    }
  }, [t]);

  const refreshDevices = useCallback(async () => {
    setLoading(true);
    const res = await refreshMiotCamera();
    if (res.code === 0) {
      await fetchDevices();
    } else {
      message.error(res.message || t('deviceManage.refreshDeviceListFailed'));
    }
    setLoading(false);
  }, [fetchDevices, t]);

  const addRtspSource = useCallback(async (payload) => {
    const res = await createRtspSource(payload);
    if (res.code === 0) {
      message.success(t('deviceManage.addRtspSuccess'));
      await fetchDevices();
      return true;
    }
    message.error(res.message || t('deviceManage.addRtspFailed'));
    return false;
  }, [fetchDevices, t]);

  const removeRtspSource = useCallback(async (sourceId) => {
    const res = await deleteRtspSource(sourceId);
    if (res.code === 0) {
      message.success(t('deviceManage.deleteRtspSuccess'));
      await fetchDevices();
      return true;
    }
    message.error(res.message || t('deviceManage.deleteRtspFailed'));
    return false;
  }, [fetchDevices, t]);

  useEffect(() => {
    fetchDevices();
  }, [fetchDevices]);

  return {
    devices,
    loading,
    error,
    refreshDevices,
    addRtspSource,
    removeRtspSource
  };
};
