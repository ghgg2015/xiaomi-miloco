/**
 * Copyright (C) 2025 Xiaomi Corporation
 * This software may be used and distributed according to the terms of the Xiaomi Miloco License Agreement.
 */

import React from 'react';
import { Button, Form, Input, Modal, Switch } from 'antd';
import { useTranslation } from 'react-i18next';
import { Header, Icon, PageContent } from '@/components';
import { DeviceList } from './components';
import { useDevices } from './hooks/useDevices';
import styles from './index.module.less';

/**
 * DeviceManage Page - Device management page for viewing and managing connected devices
 * 设备管理页面 - 用于查看和管理已连接设备的页面
 *
 * @returns {JSX.Element} Device management page component
 */
const DeviceManage = () => {
  const { t } = useTranslation();
  const [modalOpen, setModalOpen] = React.useState(false);
  const [form] = Form.useForm();
  const { devices, loading, refreshDevices, addRtspSource, removeRtspSource } = useDevices();

  const handleAddRtsp = async () => {
    const values = await form.validateFields();
    const success = await addRtspSource(values);
    if (success) {
      form.resetFields();
      setModalOpen(false);
    }
  };

  return (
    <>
      <PageContent
        Header={(
          <Header
            title={t('home.menu.deviceManage')}
            rightContent={<div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px'
              }}
            >
              <Button type="primary" onClick={() => setModalOpen(true)}>
                {t('deviceManage.addRtsp')}
              </Button>
              <div
                style={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}
                onClick={refreshDevices}
              >
                <Icon
                  name="refresh"
                  size={15}
                  style={{ color: 'var(--text-color)' }}
                />
                <span style={{ fontSize: '14px', color: 'var(--text-color)', marginLeft: '6px' }}>{t('common.refresh')}</span>
              </div>
            </div>
            }
          />
        )}
        loading={loading}
        showEmptyContent={!loading && devices.length === 0}
        emptyContentProps={{
          description: t('deviceManage.noDevice'),
          imageStyle: { width: 72, height: 72 },
        }}
      >
        <DeviceList devices={devices} onDelete={removeRtspSource} />
      </PageContent>
      <Modal
        title={t('deviceManage.addRtsp')}
        open={modalOpen}
        onOk={handleAddRtsp}
        onCancel={() => setModalOpen(false)}
        destroyOnHidden
      >
        <Form form={form} layout="vertical" initialValues={{ enabled: true, home_name: 'RTSP', room_name: 'Custom Camera' }}>
          <Form.Item name="name" label={t('deviceManage.rtspName')} rules={[{ required: true }]}>
            <Input placeholder="Front Gate Camera" />
          </Form.Item>
          <Form.Item name="rtsp_url" label={t('deviceManage.rtspUrl')} rules={[{ required: true }]}>
            <Input placeholder="rtsp://192.168.1.10:554/stream1" />
          </Form.Item>
          <Form.Item name="username" label={t('deviceManage.rtspUsername')}>
            <Input placeholder="admin" />
          </Form.Item>
          <Form.Item name="password" label={t('deviceManage.rtspPassword')}>
            <Input.Password placeholder="password" />
          </Form.Item>
          <Form.Item name="home_name" label={t('deviceManage.rtspGroup')}>
            <Input placeholder="RTSP" />
          </Form.Item>
          <Form.Item name="room_name" label={t('deviceManage.rtspRoom')}>
            <Input placeholder="Custom Camera" />
          </Form.Item>
          <Form.Item name="enabled" label={t('deviceManage.rtspEnabled')} valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
};

export default DeviceManage;
